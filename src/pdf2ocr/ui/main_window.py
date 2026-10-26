"""The main application window."""

import logging
import os
import re
import time
import urllib.parse
import urllib.request

from PyQt5.QtCore import QSize, Qt, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices, QIcon, QKeySequence, QPixmap
from PyQt5.QtWidgets import (QAction, QApplication, QFileDialog, QFrame, QHBoxLayout, QInputDialog,
                             QLabel, QMainWindow, QMenu, QMessageBox, QProgressBar, QPushButton,
                             QSplitter, QStackedWidget, QToolButton, QVBoxLayout, QWidget)

from .. import APP_NAME, DONATE_URL, FEEDBACK_URL, session
from ..diagnostics import collect as collect_diagnostics
from ..document import FILE_DIALOG_FILTER, Method, Status, expand_paths, is_supported, load_pages
from dataclasses import replace as dataclass_replace

from ..engine import (PageJob, detect_page_corners, recognize as recognize_page, rotate_box,
                      rotate_clockwise, straighten, straighten_photo)
from ..exporters import (ExportPage, export_docx, export_markdown, export_odt, export_searchable_pdf, export_text,
                         join_text)
from ..jobs import BackgroundCall, JobManager
from ..tables import build_table, describe, export_csv, export_xlsx, is_table, to_tsv
from ..languages import default_languages, display_name
from .. import scanner
from ..screenshot import ScreenCapture
from ..tools import ToolError, missing_tools
from .dialogs import AboutDialog, QuickCaptureDialog, SettingsDialog, open_url
from .empty_state import EmptyState
from .languages_ui import LanguageManager, LanguagePicker, summary
from .page_list import PageList
from .scan_dialog import ScanDialog
from .text_panel import TextPanel
from .theme import theme
from .viewer import ViewerPanel
from .widgets import Banner, refresh_icons, tool_button

log = logging.getLogger(__name__)

MAX_DOWNLOAD_BYTES = 300 * 1024 * 1024
CONTENT_TYPES = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg",
                 "image/tiff": ".tif", "image/webp": ".webp", "image/gif": ".gif", "image/bmp": ".bmp"}
OCR_SETTING_KEYS = ["ocr/page_layout", "ocr/pdf_dpi", "ocr/use_text_layer", "ocr/preserve_spaces",
                    "image/auto_rotate", "image/deskew", "image/upscale_small", "image/improve_contrast",
                    "image/black_and_white", "image/remove_noise"]


class MainWindow(QMainWindow):
    def __init__(self, settings, store, workdir, icon_path):
        super().__init__()
        self.settings = settings
        self.store = store
        self.workdir = workdir
        self.icon_path = icon_path
        self.pages = {}
        self.unsaved = False
        self._calls = set()
        self._batch_started = 0.0
        self._pasted = 0
        self._banner_callback = None
        self.capture = None
        self.scan_dialog = None
        self._scanned = 0

        installed = store.installed()
        chosen = [code for code in settings.get("ocr/languages") if code in installed]
        self.languages = chosen or default_languages(installed, _locale_name())

        self.jobs = JobManager(workdir, self)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(1500)
        self._save_timer.timeout.connect(self._save_session)
        self._saving = False
        self._save_again = False
        self.setWindowTitle(APP_NAME)
        if icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setAcceptDrops(True)
        self.setMinimumSize(860, 560)

        self._build_ui()
        self._build_actions()
        self._connect_jobs()
        self._apply_result_settings()
        self._restore_geometry()
        self._update_languages_ui()
        self._update_state()
        self._check_environment()
        if self.settings.get("ui/restore_session"):
            self._restore_session()

    # ======================================================================
    # Construction
    # ======================================================================

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        self.banner = Banner()
        self.banner.action_clicked.connect(self._banner_action)
        banner_wrap = QHBoxLayout()
        banner_wrap.setContentsMargins(12, 8, 12, 0)
        banner_wrap.addWidget(self.banner)
        root.addLayout(banner_wrap)

        self.stack = QStackedWidget()
        self.empty = EmptyState()
        self.empty.open_clicked.connect(self.open_files)
        self.empty.paste_clicked.connect(self.paste)
        self.empty.screenshot_clicked.connect(self.take_screenshot)
        self.empty.scan_clicked.connect(self.open_scanner)
        self.empty.url_clicked.connect(self.open_url_dialog)
        self.empty.languages_clicked.connect(lambda: self.picker.popup_below(self.empty.language_line))
        self.stack.addWidget(self.empty)

        self.page_list = PageList(self.pages)
        self.page_list.setMinimumWidth(150)
        self.page_list.current_page_changed.connect(self._show_page)
        self.page_list.context_menu_requested.connect(self._page_menu)
        self.page_list.order_changed.connect(self._refresh_all_text)
        self.page_list.order_changed.connect(self._schedule_save)
        self.viewer = ViewerPanel()
        self.viewer.rotate_requested.connect(self.rotate_pages)
        self.viewer.perspective_requested.connect(self.start_perspective)
        self.viewer.perspective_applied.connect(self.apply_perspective)
        self.viewer.viewer.area_selected.connect(self._read_area)
        self.viewer.card.copy_clicked.connect(self._copy_area_text)
        self.viewer.card.copy_table_clicked.connect(self._copy_area_table)
        self._area_words = []
        self.viewer.card.apply_page.connect(lambda: self._apply_area(all_pages=False))
        self.viewer.card.apply_all.connect(lambda: self._apply_area(all_pages=True))
        self.viewer.card.closed.connect(self.viewer.viewer.clear_selection)
        self._area = None
        self._area_request = 0
        self.text_panel = TextPanel()
        self.text_panel.text_edited.connect(self._text_edited)
        self.text_panel.rerun_requested.connect(self._rerun_page)
        self.text_panel.area_reset_requested.connect(lambda page_id: self.use_whole_page([page_id]))
        self.viewer.viewer.word_clicked.connect(self.text_panel.select_word)
        self.text_panel.words_focused.connect(self.viewer.viewer.focus_boxes)
        self.text_panel.mode_changed.connect(lambda _all: self._refresh_all_text())
        self.text_panel.mode_changed.connect(lambda _all: self._find_refresh())
        bar = self.text_panel.find_bar
        bar.search_changed.connect(self._find)
        bar.step.connect(self._find_step)
        bar.replace_one.connect(self._replace_one)
        bar.replace_all.connect(self._replace_all)
        bar.closed.connect(self._find_closed)
        self._matches = []
        self._match_index = -1
        self._search = ("", False)

        self.content_split = QSplitter(Qt.Horizontal)
        self.content_split.addWidget(self.viewer)
        self.content_split.addWidget(self.text_panel)
        self.content_split.setChildrenCollapsible(False)
        self.content_split.setSizes([560, 520])
        self.main_split = QSplitter(Qt.Horizontal)
        self.main_split.addWidget(self.page_list)
        self.main_split.addWidget(self.content_split)
        self.main_split.setStretchFactor(1, 1)
        self.main_split.setSizes([200, 1000])
        self.stack.addWidget(self.main_split)
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        status = self.statusBar()
        status.setSizeGripEnabled(False)
        self.progress_label = QLabel()
        self.progress_label.setObjectName("Muted")
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(180)
        status.addPermanentWidget(self.progress_label)
        status.addPermanentWidget(self.progress)
        self.progress_label.hide()
        self.progress.hide()

        self.picker = LanguagePicker(self.store, self.languages, self)
        self.picker.languages_changed.connect(self._languages_changed)
        self.picker.manage_requested.connect(self.manage_languages)

    def _build_header(self):
        header = QFrame()
        header.setObjectName("Header")
        row = QHBoxLayout(header)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(4)

        logo = QLabel()
        if self.icon_path and os.path.exists(self.icon_path):
            logo.setPixmap(QPixmap(self.icon_path).scaled(26, 26, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        title = QLabel(APP_NAME)
        title.setObjectName("AppTitle")
        row.addWidget(logo)
        row.addWidget(title)
        row.addSpacing(16)

        self.open_button = tool_button("open", "Open PDFs or images (Ctrl+O)", text="Open")
        self.open_button.clicked.connect(self.open_files)
        self.open_more_button = tool_button("chevron", "More ways to open: folder, web address", size=14)
        self.open_more_button.setPopupMode(QToolButton.InstantPopup)
        self.open_more_button.setStyleSheet("padding: 6px 3px;")
        self.paste_button = tool_button("paste", "Paste an image or screenshot from the clipboard (Ctrl+V)",
                                        text="Paste")
        self.paste_button.clicked.connect(self.paste)
        self.shot_button = tool_button("screenshot", "Capture an area of the screen (Ctrl+Shift+A)\n"
                                       "Tip: set up a global shortcut in ⋮ → Quick capture shortcut",
                                       text="Screenshot")
        self.shot_button.clicked.connect(self.take_screenshot)
        self.scan_button = tool_button("scanner", "Scan pages from a scanner", text="Scan")
        self.scan_button.clicked.connect(self.open_scanner)
        for button in (self.open_button, self.open_more_button, self.paste_button, self.shot_button,
                       self.scan_button):
            row.addWidget(button)
        row.addSpacing(12)

        self.language_button = tool_button("globe", "Languages in your document — choose them for best accuracy",
                                           text=" ", outlined=True)
        self.language_button.clicked.connect(lambda: self.picker.popup_below(self.language_button))
        row.addWidget(self.language_button)
        row.addStretch(1)

        self.recognize_button = QPushButton()
        self.recognize_button.setObjectName("Primary")
        self.recognize_button.setCursor(Qt.PointingHandCursor)
        self.recognize_button.setIconSize(QSize(18, 18))
        self.recognize_button.clicked.connect(self._recognize_clicked)
        row.addWidget(self.recognize_button)
        row.addSpacing(4)

        self.export_button = tool_button("export", "Save or copy the recognized text", text="Export",
                                         outlined=True)
        self.export_button.setPopupMode(QToolButton.InstantPopup)
        row.addWidget(self.export_button)
        self.settings_button = tool_button("settings", "Settings (Ctrl+,)")
        self.settings_button.clicked.connect(self.open_settings)
        self.more_button = tool_button("more", "More")
        self.more_button.setPopupMode(QToolButton.InstantPopup)
        row.addWidget(self.settings_button)
        row.addWidget(self.more_button)
        return header

    def _action(self, text, slot, shortcut=None, icon=None, context=Qt.WindowShortcut):
        action = QAction(text, self)
        if icon:
            action.setIcon(theme().icon(icon, size=16))
            action.setData(icon)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(context)
        action.triggered.connect(lambda _checked=False: slot())
        self.addAction(action)
        return action

    def _build_actions(self):
        a = self._action
        self.act_open = a("Open files…", self.open_files, "Ctrl+O", "open")
        self.act_folder = a("Open folder…", self.open_folder, "Ctrl+Shift+O", "folder")
        self.act_url = a("Open from web address…", self.open_url_dialog, "Ctrl+L", "link")
        self.act_scan = a("Scan…", self.open_scanner, "Ctrl+Shift+N", "scanner")
        open_menu = QMenu(self)
        open_menu.addActions([self.act_open, self.act_folder, self.act_url, self.act_scan])
        self.recent_menu = open_menu.addMenu(theme().icon("document", size=16), "Open recent")
        self.recent_menu.aboutToShow.connect(self._fill_recent_menu)
        self.open_more_button.setMenu(open_menu)

        self.act_paste = a("Paste image", self.paste, QKeySequence.Paste, "paste")
        self.act_shot = a("Capture screen area", self.take_screenshot, "Ctrl+Shift+A", "screenshot")
        self.act_recognize = a("Recognize", self._recognize_clicked, "Ctrl+R", "scan")

        self.act_txt = a("Text file (.txt)…", lambda: self.export("txt"), "Ctrl+S", "document")
        self.act_docx = a("Word document (.docx)…", lambda: self.export("docx"), None, "document")
        self.act_odt = a("LibreOffice document (.odt)…", lambda: self.export("odt"), None, "document")
        self.act_md = a("Markdown (.md)…", lambda: self.export("md"), None, "text")
        self.act_xlsx = a("Tables → Excel (.xlsx)…", lambda: self.export_tables("xlsx"), None, "table")
        self.act_csv = a("Table on this page → CSV…", lambda: self.export_tables("csv"), None, "table")
        self.act_pdf = a("Searchable PDF…", lambda: self.export("pdf"), "Ctrl+Shift+S", "pages")
        self.act_copy_all = a("Copy all text", self.copy_all_text, "Ctrl+Shift+C", "copy")
        export_menu = QMenu(self)
        export_menu.addActions([self.act_txt, self.act_docx, self.act_odt, self.act_md, self.act_pdf])
        export_menu.addSeparator()
        export_menu.addActions([self.act_xlsx, self.act_csv])
        export_menu.addSeparator()
        export_menu.addAction(self.act_copy_all)
        self.export_button.setMenu(export_menu)

        self.act_settings = a("Settings…", self.open_settings, "Ctrl+,", "settings")
        self.act_languages = a("Languages…", self.manage_languages, None, "globe")
        self.act_theme = a("Switch light / dark", self.toggle_theme, "Ctrl+Shift+L", "theme")
        self.act_close_all = a("Close all documents", self.close_all, "Ctrl+W", "close")
        self.act_quick = a("Quick capture shortcut…", lambda: QuickCaptureDialog(self).exec_(), None, "screenshot")
        self.act_about = a("About PDF2OCR", self.show_about, "F1", "info")
        self.act_feedback = a("Report a problem", self.report_problem, None, "warning")
        self.act_donate = a("Support development", lambda: open_url(DONATE_URL), None, "heart")
        a("Quit", self.close, "Ctrl+Q")
        a("Select an area to read", self._toggle_select_mode, "Ctrl+E")
        a("Find", lambda: self.open_find(False), QKeySequence.Find)
        a("Replace", lambda: self.open_find(True), "Ctrl+H")
        a("Find next", lambda: self._find_step(1), QKeySequence.FindNext)
        a("Find previous", lambda: self._find_step(-1), QKeySequence.FindPrevious)
        a("Next page", lambda: self.page_list.step(1), "Ctrl+PgDown")
        a("Previous page", lambda: self.page_list.step(-1), "Ctrl+PgUp")
        more = QMenu(self)
        more.addActions([self.act_quick, self.act_languages, self.act_theme, self.act_close_all])
        more.addSeparator()
        more.addActions([self.act_about, self.act_feedback, self.act_donate])
        self.more_button.setMenu(more)

        remove = QAction("Remove pages", self.page_list)
        remove.setShortcut(QKeySequence.Delete)
        remove.setShortcutContext(Qt.WidgetShortcut)
        remove.triggered.connect(self.remove_selected_pages)
        self.page_list.addAction(remove)

    def _connect_jobs(self):
        self.jobs.ocr_started.connect(self._ocr_started)
        self.jobs.ocr_finished.connect(self._ocr_finished)
        self.jobs.ocr_failed.connect(self._ocr_failed)
        self.jobs.ocr_cancelled.connect(self._ocr_cancelled)
        self.jobs.batch_progress.connect(self._batch_progress)
        self.jobs.batch_finished.connect(self._batch_finished)
        self.jobs.preview_ready.connect(self._preview_ready)
        self.jobs.thumbnail_ready.connect(self._thumbnail_ready)

    def _check_environment(self):
        missing = missing_tools()
        if "tesseract" in missing:
            self.show_banner("Tesseract OCR is not installed, so text can't be recognized. "
                             "Install it with “sudo apt install tesseract-ocr” and restart.", icon="warning")
        elif missing:
            self.show_banner(f"Some PDF tools are missing ({', '.join(missing)}). "
                             "Install “poppler-utils” to open PDF files.", icon="warning")
        elif not self.store.installed():
            self.show_banner("No OCR languages are installed.", "Get languages", self.manage_languages,
                             icon="warning")

    # ======================================================================
    # Opening documents
    # ======================================================================

    def _dialog_options(self):
        # Inside the snap the Qt dialog is the reliable choice; elsewhere use the native one.
        return QFileDialog.DontUseNativeDialog if os.environ.get("SNAP") else QFileDialog.Options()

    def open_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Open documents", self.settings.get("ui/last_dir"),
                                                FILE_DIALOG_FILTER, options=self._dialog_options())
        if paths:
            self.settings.set("ui/last_dir", os.path.dirname(paths[0]))
            self.add_files(paths)

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Open a folder of scans", self.settings.get("ui/last_dir"),
                                                  options=self._dialog_options() | QFileDialog.ShowDirsOnly)
        if folder:
            self.settings.set("ui/last_dir", folder)
            self.add_files([folder])

    def add_files(self, paths, names=None):
        """Load files in the background; names optionally overrides display names."""
        names = names or {}
        self._remember_recent([p for p in paths if not session.is_inside(p, self.workdir)
                               and not session.is_inside(p, session.session_dir())])
        files = expand_paths(paths)
        if not files:
            self.show_banner("No supported files were found.", icon="warning")
            return

        def work(_progress, _token):
            pages, errors = [], []
            for path in files:
                try:
                    pages += load_pages(path, names.get(path))
                except ToolError as error:
                    errors.append((names.get(path) or os.path.basename(path), str(error)))
            return pages, errors

        self.statusBar().showMessage("Opening…")
        self._run(work, self._files_loaded)

    def _files_loaded(self, result):
        pages, errors = result
        self.statusBar().clearMessage()
        if errors:
            details = "; ".join(f"{name}: {reason}" for name, reason in errors[:3])
            more = f" (and {len(errors) - 3} more)" if len(errors) > 3 else ""
            self.show_banner(f"Couldn't open {len(errors)} file{'s' if len(errors) > 1 else ''} — {details}{more}",
                             icon="warning")
        if not pages:
            return
        for page in pages:
            self.pages[page.id] = page
        self.page_list.add_pages(pages)
        for page in pages:
            self.jobs.request_thumbnail(self._job(page))
        self.stack.setCurrentWidget(self.main_split)
        self.page_list.select_id(pages[0].id)
        if self.settings.get("ocr/auto_start"):
            self.recognize([page.id for page in pages])
        self._update_state()
        self._schedule_save()

    def paste(self):
        mime = QApplication.clipboard().mimeData()
        if mime is None:
            return
        local = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()] if mime.hasUrls() else []
        if local:
            self.add_files(local)
        elif mime.hasImage():
            image = QApplication.clipboard().image()
            if image.isNull():
                return
            self._pasted += 1
            path = os.path.join(self.workdir, f"pasted-{self._pasted}.png")
            image.save(path, "PNG")
            self.add_files([path], {path: f"Pasted image {self._pasted}"})
        elif mime.hasText() and mime.text().strip().startswith(("http://", "https://")):
            self.download(mime.text().strip())
        else:
            self.show_banner("The clipboard doesn't contain an image. Copy a screenshot first "
                             "(on most desktops Shift+PrtSc or Ctrl+Shift+PrtSc copies an area), "
                             "or use the Screenshot button.", icon="info")

    def take_screenshot(self):
        if self.capture is not None:
            return
        self.capture = ScreenCapture(self, self.workdir)
        self.capture.captured.connect(self._screenshot_taken)
        self.capture.failed.connect(lambda message: self.show_banner(message, icon="warning"))
        self.capture.finished.connect(self._screenshot_finished)
        self.capture.start()

    def open_scanner(self):
        if not scanner.available():
            self.show_banner("Scanning needs SANE, the Linux scanner system. Install it with "
                             "“sudo apt install sane-utils” and restart PDF2OCR.", icon="warning")
            return
        if self.scan_dialog is None:
            self.scan_dialog = ScanDialog(self.settings, self.workdir, self)
            self.scan_dialog.pages_scanned.connect(self._pages_scanned)
        self.scan_dialog.show()
        self.scan_dialog.raise_()
        self.scan_dialog.activateWindow()

    def _pages_scanned(self, paths):
        names = {}
        for path in paths:
            self._scanned += 1
            names[path] = f"Scan {self._scanned}"
        self.add_files(paths, names)

    def _screenshot_taken(self, path):
        self._pasted += 1
        self.add_files([path], {path: f"Screenshot {self._pasted}"})

    def _screenshot_finished(self):
        self.capture.deleteLater()
        self.capture = None

    def open_url_dialog(self):
        url, ok = QInputDialog.getText(self, "Open from web address",
                                       "Link to a PDF or image (it will be downloaded, then processed offline):")
        if ok and url.strip():
            self.download(url.strip())

    def download(self, url):
        if not url.lower().startswith(("http://", "https://")):
            self.show_banner("Please enter a link starting with http:// or https://", icon="warning")
            return
        workdir = self.workdir

        def work(progress, token):
            request = urllib.request.Request(url, headers={"User-Agent": "PDF2OCR"})
            with urllib.request.urlopen(request, timeout=30) as response:
                name = os.path.basename(urllib.parse.unquote(urllib.parse.urlparse(response.geturl()).path)) or "download"
                content_type = response.headers.get_content_type()
                if not is_supported(name):
                    name = os.path.splitext(name)[0] + CONTENT_TYPES.get(content_type, "")
                if not is_supported(name):
                    raise ToolError(f"The link doesn't point to a PDF or image ({content_type}).")
                folder = os.path.join(workdir, f"download-{os.urandom(3).hex()}")
                os.makedirs(folder)
                target = os.path.join(folder, name)
                total = int(response.headers.get("Content-Length") or 0)
                received = 0
                with open(target, "wb") as handle:
                    while True:
                        token.check()
                        chunk = response.read(256 * 1024)
                        if not chunk:
                            break
                        received += len(chunk)
                        if received > MAX_DOWNLOAD_BYTES:
                            raise ToolError("The file is too large (over 300 MB).")
                        handle.write(chunk)
                        progress(received, total)
            return target

        def failed(message):
            self.show_banner(f"Download failed: {message}", icon="warning")

        self.statusBar().showMessage("Downloading…")
        self._run(work, lambda path: self.add_files([path]), failed)

    # ---- drag & drop ----------------------------------------------------

    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls() or mime.hasImage():
            event.acceptProposedAction()
            self.empty.set_drag_active(True)

    def dragLeaveEvent(self, event):
        self.empty.set_drag_active(False)

    def dropEvent(self, event):
        self.empty.set_drag_active(False)
        mime = event.mimeData()
        local = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
        remote = [url.toString() for url in mime.urls() if url.scheme() in ("http", "https")]
        if local:
            self.add_files(local)
        for url in remote:
            self.download(url)
        if not local and not remote and mime.hasImage():
            self._pasted += 1
            path = os.path.join(self.workdir, f"dropped-{self._pasted}.png")
            mime.imageData().save(path, "PNG")
            self.add_files([path], {path: f"Dropped image {self._pasted}"})
        event.acceptProposedAction()

    # ======================================================================
    # Recognition
    # ======================================================================

    def _job(self, page):
        kind, source, index = page.image_source
        return PageJob(page.id, kind, source, index, page.user_rotation, page.force_ocr,
                       crop=page.crop, auto_rotation=page.auto_rotation, skew=page.skew)

    def _ocr_options(self):
        return self.settings.ocr_options(self.store, self.languages)

    def recognize(self, ids):
        if "tesseract" in missing_tools():
            self._check_environment()
            return
        jobs = []
        for page_id in ids:
            page = self.pages.get(page_id)
            if page is None or page.status in (Status.QUEUED, Status.WORKING):
                continue
            page.status = Status.QUEUED
            page.error = ""
            jobs.append(self._job(page))
            self.page_list.refresh_page(page_id)
        if not jobs:
            return
        if not self.jobs.busy:
            self._batch_started = time.monotonic()
        self.jobs.recognize(jobs, self._ocr_options(), self.settings.get("ocr/parallel_pages"))
        self._refresh_current_text()
        self._update_state()

    def _recognize_clicked(self):
        if self.jobs.busy:
            self.jobs.cancel()
            self.statusBar().showMessage("Stopping…")
            return
        ordered = [self.pages[i] for i in self.page_list.ordered_ids()]
        pending = [p.id for p in ordered if p.status in (Status.PENDING, Status.ERROR)]
        if pending:
            self.recognize(pending)
            return
        if not ordered:
            return
        if any(p.edited for p in ordered):
            answer = QMessageBox.question(self, "Recognize again?",
                                          "All pages will be recognized again and your edits will be replaced.",
                                          QMessageBox.Yes | QMessageBox.Cancel)
            if answer != QMessageBox.Yes:
                return
        self.recognize([p.id for p in ordered])

    def _rerun_page(self, page_id, force_ocr):
        page = self.pages.get(page_id)
        if page is None:
            return
        if page.edited and QMessageBox.question(
                self, "Recognize again?", "Your edits to this page will be replaced.",
                QMessageBox.Yes | QMessageBox.Cancel) != QMessageBox.Yes:
            return
        page.force_ocr = page.force_ocr or force_ocr
        self.recognize([page_id])

    def _ocr_started(self, page_id):
        page = self.pages.get(page_id)
        if page:
            page.status = Status.WORKING
            self.page_list.refresh_page(page_id)
            self._refresh_current_text(page_id)

    def _ocr_finished(self, page_id, result):
        page = self.pages.get(page_id)
        if page is None:
            return
        page.status = Status.DONE
        page.text = result.text
        page.edited = False
        page.method = result.method
        page.languages = result.languages
        page.confidence = result.confidence
        page.words = result.words or []
        page.auto_rotation = result.auto_rotation
        page.skew = result.skew
        page.text_pdf = result.text_pdf
        self.unsaved = True
        self._schedule_save()
        self.page_list.refresh_page(page_id)
        if page_id == self.page_list.current_id():
            self._update_viewer_words(page)
            self.viewer.viewer.set_rotation(page.total_rotation, page.skew)
        self._refresh_current_text(page_id)
        self._refresh_all_text()

    def _ocr_failed(self, page_id, message):
        page = self.pages.get(page_id)
        if page is None:
            return
        page.status = Status.ERROR
        page.error = message
        self.page_list.refresh_page(page_id)
        self._refresh_current_text(page_id)

    def _ocr_cancelled(self, page_id):
        page = self.pages.get(page_id)
        if page is not None and page.status in (Status.QUEUED, Status.WORKING):
            page.status = Status.DONE if page.method else Status.PENDING
            self.page_list.refresh_page(page_id)
            self._refresh_current_text(page_id)

    def _batch_progress(self, done, total):
        self.progress.setRange(0, total)
        self.progress.setValue(done)
        self.progress_label.setText(f"Recognizing page {min(done + 1, total)} of {total}")
        self.progress.show()
        self.progress_label.show()
        self._update_state()

    def _batch_finished(self, cancelled):
        self.progress.hide()
        self.progress_label.hide()
        seconds = time.monotonic() - self._batch_started
        failed = sum(1 for p in self.pages.values() if p.status == Status.ERROR)
        if cancelled:
            self.statusBar().showMessage("Recognition stopped.", 6000)
        else:
            done = sum(1 for p in self.pages.values() if p.status == Status.DONE)
            message = f"Done — {done} page{'s' if done != 1 else ''} ready in {seconds:.0f} s"
            if failed:
                message += f", {failed} failed"
            self.statusBar().showMessage(message, 10000)
        self._update_state()

    # ======================================================================
    # Current page
    # ======================================================================

    def _show_page(self, page_id):
        page = self.pages.get(page_id)
        self.text_panel.show_page(page)
        self.viewer.card.hide()
        if page is None:
            self.viewer.viewer.show_message("")
            return
        self.viewer.viewer.set_area(page.crop)
        self._update_viewer_words(page)
        self._find_highlight_page()
        if page.preview_path and os.path.exists(page.preview_path):
            self.viewer.viewer.set_image(QPixmap(page.preview_path), page.total_rotation, page.skew)
        else:
            self.viewer.viewer.show_message("Loading page…")
            self.jobs.request_preview(self._job(page))
        self._update_state()

    def _preview_ready(self, page_id, path):
        page = self.pages.get(page_id)
        if page is None:
            return
        page.preview_path = path or None
        if page_id == self.page_list.current_id():
            if path:
                self.viewer.viewer.set_area(page.crop)
                self._update_viewer_words(page)
                self.viewer.viewer.set_image(QPixmap(path), page.total_rotation, page.skew)
            else:
                self.viewer.viewer.show_message("This page can't be displayed.")

    def _update_viewer_words(self, page):
        """Word boxes for clicking on the image, plus marks on uncertain words."""
        if page is None or page.status != Status.DONE:
            self.viewer.viewer.set_words([], [])
            return
        threshold = self.settings.get("results/uncertain_below")
        flag = self.settings.get("results/highlight_uncertain") and page.method == Method.OCR
        marks = [box for _word, conf, box in page.words if flag and conf < threshold]
        self.viewer.viewer.set_words([box for _word, _conf, box in page.words], marks)

    def _thumbnail_ready(self, page_id, path):
        if page_id in self.pages and path:
            self.page_list.thumbnails[page_id] = QPixmap(path)
            self.page_list.refresh_page(page_id)
        if path and os.path.exists(path):
            os.remove(path)

    def _refresh_current_text(self, page_id=None):
        current = self.page_list.current_id()
        if page_id is None or page_id == current:
            self.text_panel.show_page(self.pages.get(current))
            self._update_state()

    def _refresh_all_text(self):
        if self.text_panel.showing_all:
            self.text_panel.show_all(join_text(self._export_pages(only_done=True),
                                               self.settings.get("results/page_separators")))

    def _text_edited(self, page_id, text):
        page = self.pages.get(page_id)
        if page:
            page.text = text
            page.edited = True
            self.unsaved = True
            self._schedule_save()
            if self.text_panel.find_bar.isVisible() and self._search[0]:
                self._find_refresh(keep_position=True)

    def rotate_pages(self, delta):
        ids = self.page_list.selected_ids() or [self.page_list.current_id()]
        rerun = []
        for page_id in ids:
            page = self.pages.get(page_id)
            if page is None:
                continue
            page.user_rotation = (page.user_rotation + delta) % 360
            page.crop = None  # the area no longer matches the rotated page
            if page.method == Method.TEXT_LAYER:
                # Exact PDF text isn't re-read, so turn its word boxes with the page.
                page.words = [(w, c, rotate_box(b, delta)) for w, c, b in page.words]
            self.page_list.refresh_page(page_id)
            if page.status == Status.DONE and page.method == Method.OCR and not page.edited:
                rerun.append(page_id)
        current = self.pages.get(self.page_list.current_id())
        if current:
            self.viewer.viewer.set_area(current.crop)
            self._update_viewer_words(current)
            self.viewer.viewer.set_rotation(current.total_rotation, current.skew)
        if rerun:
            self.recognize(rerun)
        self._schedule_save()

    # ---- find & replace -------------------------------------------------

    def open_find(self, replace_mode):
        if self.stack.currentWidget() is not self.main_split:
            return
        selected = self.text_panel.editor.textCursor().selectedText()
        self.text_panel.find_bar.open(replace_mode, selected)
        self.text_panel.find_bar.set_replace_enabled(not self.text_panel.showing_all)

    def _pattern(self):
        text, case = self._search
        return re.compile(re.escape(text), 0 if case else re.IGNORECASE) if text else None

    def _compute_matches(self):
        pattern = self._pattern()
        if pattern is None:
            return []
        if self.text_panel.showing_all:
            return [(None, m.start(), m.end()) for m in pattern.finditer(self.text_panel.editor.toPlainText())]
        matches = []
        for page in self._ordered_pages():
            if page.status == Status.DONE:
                matches += [(page.id, m.start(), m.end()) for m in pattern.finditer(page.text)]
        return matches

    def _find(self, text, case):
        self._search = (text, case)
        self._matches = self._compute_matches()
        self._match_index = -1
        if not self._matches:
            self._find_update_count()
            self._find_highlight_page()
            return
        # Start from the current page and cursor, like a browser's find.
        order = {pid: n for n, pid in enumerate(self.page_list.ordered_ids())}
        here = (order.get(self.page_list.current_id(), 0), self.text_panel.editor.textCursor().selectionStart())
        start = 0
        for index, (pid, begin, _end) in enumerate(self._matches):
            if (order.get(pid, 0), begin) >= here:
                start = index
                break
        self._go_to_match(start)

    def _find_refresh(self, keep_position=False):
        if not self.text_panel.find_bar.isVisible():
            return
        if keep_position and self._match_index >= 0 and self._matches:
            pid, begin, _end = self._matches[min(self._match_index, len(self._matches) - 1)]
            self._matches = self._compute_matches()
            index = next((i for i, (p, b, _e) in enumerate(self._matches) if p == pid and b >= begin), -1)
            self._match_index = index
            self._find_highlight_page()
            self._find_update_count()
        else:
            self._find(*self._search)
        self.text_panel.find_bar.set_replace_enabled(not self.text_panel.showing_all)

    def _find_step(self, delta):
        if not self.text_panel.find_bar.isVisible():
            self.open_find(False)
            return
        if not self._matches:
            return
        self._go_to_match((self._match_index + delta) % len(self._matches))

    def _go_to_match(self, index):
        self._match_index = index
        pid, _begin, _end = self._matches[index]
        if pid is not None and pid != self.page_list.current_id():
            self.page_list.select_id(pid)  # shows the page, then highlights below
        self._find_highlight_page()
        self._find_update_count()

    def _find_highlight_page(self):
        if not self.text_panel.find_bar.isVisible() or not self._matches:
            self.text_panel.set_search_highlights([])
            return
        pid = None if self.text_panel.showing_all else self.page_list.current_id()
        ranges = [(b, e) for p, b, e in self._matches if p == pid]
        current = None
        if 0 <= self._match_index < len(self._matches):
            p, b, e = self._matches[self._match_index]
            current = (b, e) if p == pid else None
        self.text_panel.set_search_highlights(ranges, current)

    def _find_update_count(self):
        pages = len({pid for pid, _b, _e in self._matches})
        current = self._match_index + 1 if self._match_index >= 0 else 0
        self.text_panel.find_bar.set_count(current, len(self._matches), pages)

    def _find_closed(self):
        self._matches, self._match_index = [], -1
        self.text_panel.set_search_highlights([])
        self.text_panel.editor.setFocus()

    def _replace_one(self, replacement):
        if self.text_panel.showing_all or not (0 <= self._match_index < len(self._matches)):
            return
        pid, begin, end = self._matches[self._match_index]
        page = self.pages.get(pid)
        if page is None or page.status != Status.DONE or pid != self.page_list.current_id():
            return
        self.text_panel.replace_range(begin, end, replacement)  # -> _text_edited -> matches refresh
        self._matches = self._compute_matches()
        order = {p: n for n, p in enumerate(self.page_list.ordered_ids())}
        after = (order[pid], begin + len(replacement))
        index = next((i for i, (p, b, _e) in enumerate(self._matches) if (order.get(p, 0), b) >= after), 0)
        if self._matches:
            self._go_to_match(index)
        else:
            self._match_index = -1
            self._find_highlight_page()
            self._find_update_count()

    def _replace_all(self, replacement):
        pattern = self._pattern()
        if pattern is None or self.text_panel.showing_all:
            return
        before, total, pages = {}, 0, 0
        for page in self._ordered_pages():
            if page.status != Status.DONE:
                continue
            new_text, count = pattern.subn(lambda _m: replacement, page.text)
            if count:
                before[page.id] = (page.text, page.edited)
                page.text, page.edited = new_text, True
                total += count
                pages += 1
        if not total:
            return
        self.unsaved = True
        self._refresh_current_text()
        self._refresh_all_text()
        self._schedule_save()
        self._find(*self._search)

        def undo():
            for page_id, (text, edited) in before.items():
                page = self.pages.get(page_id)
                if page is not None:
                    page.text, page.edited = text, edited
            self._refresh_current_text()
            self._refresh_all_text()
            self._schedule_save()
            self._find_refresh()
            self.statusBar().showMessage("Replace all was undone.", 4000)

        self.show_banner(f"Replaced {total} match{'es' if total != 1 else ''} on {pages} page{'s' if pages != 1 else ''}.",
                         "Undo", undo, icon="check")

    # ---- reading a selected area ----------------------------------------

    def _toggle_select_mode(self):
        if self.stack.currentWidget() is self.main_split:
            self.viewer.select_button.toggle()

    def _read_area(self, fractions):
        page = self.pages.get(self.page_list.current_id())
        if page is None:
            return
        self._area = (page.id, fractions)
        self._area_request += 1
        request = self._area_request
        job = dataclass_replace(self._job(page), crop=fractions)
        options = self._ocr_options()
        workdir = self.workdir
        self.viewer.card.show_busy()
        self.viewer.place_overlays()

        def done(result):
            if request != self._area_request:
                return  # a newer selection replaced this one
            self._area_words = result.words or []
            note = "Exact text from the PDF." if result.method == Method.TEXT_LAYER else ""
            if result.text and self.settings.get("results/area_auto_copy"):
                QApplication.clipboard().setText(result.text)
                note = (note + " Copied to the clipboard.").strip()
            if result.method == Method.OCR and result.confidence is not None:
                note = (f"{round(result.confidence)}% confidence. " + note).strip()
            self.viewer.card.show_result(result.text, note)

        def failed(message):
            if request == self._area_request:
                self.viewer.card.show_error(message)

        self._run(lambda _progress, token: recognize_page(job, options, workdir, token), done, failed)

    # ---- perspective correction -------------------------------------------

    def start_perspective(self):
        page = self.pages.get(self.page_list.current_id())
        if page is None or not self.viewer.viewer.has_image():
            return
        inset = 0.04
        self.viewer.show_perspective(((inset, inset), (1 - inset, inset), (1 - inset, 1 - inset), (inset, 1 - inset)))
        preview, rotation, skew, page_id = page.preview_path, page.total_rotation, page.skew, page.id

        def detect(_progress, _token):
            from PIL import Image
            img = rotate_clockwise(Image.open(preview), rotation)
            return detect_page_corners(straighten(img, skew) if skew else img)

        def detected(corners):
            if corners and self.viewer.viewer.perspective_active and self.page_list.current_id() == page_id:
                self.viewer.viewer.set_perspective_corners(corners)

        if preview:
            self._run(detect, detected, lambda _m: None)

    def apply_perspective(self, corners, shape):
        page = self.pages.get(self.page_list.current_id())
        if page is None:
            return
        if page.edited and QMessageBox.question(
                self, "Straighten page?", "The page will be recognized again and your edits replaced.",
                QMessageBox.Yes | QMessageBox.Cancel) != QMessageBox.Yes:
            return
        job = self._job(page)
        out = os.path.join(self.workdir, f"flat-{page.id}-{os.urandom(3).hex()}.png")
        dpi = self.settings.get("ocr/pdf_dpi")
        self.statusBar().showMessage("Straightening the page…")

        def done(path):
            self.statusBar().clearMessage()
            if page.id not in self.pages:
                return
            if page.pre_derive is None:
                page.pre_derive = (page.user_rotation, page.auto_rotation)
            page.derived = path
            self._replace_page_image(page)
            self.show_banner("Page straightened.", "Undo", lambda: self.undo_perspective([page.id]),
                             icon="perspective")

        self._run(lambda _p, token: straighten_photo(job, corners, out, dpi, shape, token), done,
                  lambda m: self.show_banner(f"Couldn't straighten the page: {m}", icon="warning"))

    def undo_perspective(self, ids):
        for page_id in ids:
            page = self.pages.get(page_id)
            if page is None or not page.derived:
                continue
            page.derived = None
            if page.pre_derive:
                page.user_rotation, page.auto_rotation = page.pre_derive
            page.pre_derive = None
            self._replace_page_image(page)

    def _replace_page_image(self, page):
        """The page's picture changed: drop cached renders and recognize it again."""
        if page.derived:
            page.user_rotation = page.auto_rotation = 0
        page.crop = None
        page.preview_path = None
        page.reset_result()
        self.page_list.thumbnails.pop(page.id, None)
        self.jobs.request_thumbnail(self._job(page))
        if page.id == self.page_list.current_id():
            self._show_page(page.id)
        self.recognize([page.id])
        self._schedule_save()

    def _copy_area_table(self):
        rows = build_table(self._area_words)
        if not rows:
            self.viewer.card.status.setText("No words with positions found in this area.")
            return
        QApplication.clipboard().setText(to_tsv(rows))
        if is_table(rows):
            self.viewer.card.status.setText(f"Copied a table ({describe(rows)}). Paste it into a spreadsheet.")
        else:
            self.viewer.card.status.setText("No columns found; copied one line per row.")

    def export_tables(self, kind):
        pages = [p for p in self._ordered_pages() if p.status == Status.DONE]
        if kind == "csv":
            current = self.pages.get(self.page_list.current_id())
            pages = [current] if current and current.status == Status.DONE else []
        sheets = [(p.label, build_table(p.words)) for p in pages]
        sheets = [(name, rows) for name, rows in sheets if is_table(rows)]
        if not sheets:
            where = "this page" if kind == "csv" else "the recognized pages"
            self.show_banner(f"No table was found on {where}. Tip: use Select area around the table, "
                             "then “Copy as table”.", icon="info")
            return
        stem = os.path.splitext(pages[0].display_name)[0]
        extension, label = (".csv", "CSV table (*.csv)") if kind == "csv" else (".xlsx", "Excel workbook (*.xlsx)")
        suggested = os.path.join(self.settings.get("ui/last_dir"), f"{stem} tables{extension}")
        path, _ = QFileDialog.getSaveFileName(self, "Export tables", suggested, label, options=self._dialog_options())
        if not path:
            return
        if not path.lower().endswith(extension):
            path += extension
        self.settings.set("ui/last_dir", os.path.dirname(path))
        try:
            if kind == "csv":
                export_csv(sheets[0][1], path)
            else:
                export_xlsx(sheets, path)
        except OSError as error:
            self._export_failed(str(error))
            return
        self._exported(path)

    def _copy_area_text(self, text):
        if text:
            QApplication.clipboard().setText(text)
            self.viewer.card.status.setText("Copied to the clipboard.")

    def _apply_area(self, all_pages):
        if not self._area:
            return
        page_id, fractions = self._area
        ids = self.page_list.ordered_ids() if all_pages else [page_id]
        pages = [self.pages[i] for i in ids if i in self.pages]
        if any(p.edited for p in pages) and QMessageBox.question(
                self, "Read only this area?", "Your edits to the affected pages will be replaced.",
                QMessageBox.Yes | QMessageBox.Cancel) != QMessageBox.Yes:
            return
        for page in pages:
            page.crop = fractions
            if page.status in (Status.DONE, Status.ERROR):
                page.status = Status.PENDING
        self.viewer.card.hide()
        self.viewer.viewer.clear_selection()
        self.viewer.viewer.set_select_mode(False)
        current = self.pages.get(self.page_list.current_id())
        self.viewer.viewer.set_area(current.crop if current else None)
        self.recognize([p.id for p in pages])
        count = len(pages)
        self.show_banner(f"Reading only the selected area on {count} page{'s' if count > 1 else ''}.",
                         "Read whole pages", lambda: self.use_whole_page([p.id for p in pages]),
                         icon="select_area")

    def use_whole_page(self, ids):
        pages = [self.pages[i] for i in ids if i in self.pages and self.pages[i].crop]
        for page in pages:
            page.crop = None
        current = self.pages.get(self.page_list.current_id())
        self.viewer.viewer.set_area(current.crop if current else None)
        if pages:
            self.recognize([p.id for p in pages])

    def remove_selected_pages(self):
        ids = self.page_list.selected_ids()
        if not ids:
            return
        self.page_list.remove_ids(ids)
        for page_id in ids:
            self.pages.pop(page_id, None)
        if not self.pages:
            self._reset_workspace()
        self._refresh_all_text()
        self._update_state()
        self._schedule_save()

    def close_all(self):
        if not self.pages:
            return
        if not self._confirm_discard("Close all documents?"):
            return
        self.jobs.cancel()
        self.page_list.remove_ids(list(self.pages))
        self.pages.clear()
        self._reset_workspace()

    def _reset_workspace(self):
        self.unsaved = False
        self._schedule_save()
        self.stack.setCurrentWidget(self.empty)
        self.text_panel.show_page(None)
        self.viewer.viewer.show_message("")
        self.banner.hide()
        self._update_state()

    def _page_menu(self, position):
        ids = self.page_list.selected_ids()
        if not ids:
            return
        pages = [self.pages[i] for i in ids if i in self.pages]
        menu = QMenu(self)
        plural = "s" if len(ids) > 1 else ""
        menu.addAction(theme().icon("refresh", size=16), f"Recognize page{plural} again",
                       lambda: self.recognize(ids))
        if any(p.method == Method.TEXT_LAYER for p in pages):
            def force():
                for p in pages:
                    p.force_ocr = True
                self.recognize(ids)
            menu.addAction(theme().icon("scan", size=16), "Use OCR instead of the PDF's text", force)
        if any(p.crop for p in pages):
            menu.addAction(theme().icon("fit", size=16), "Read the whole page", lambda: self.use_whole_page(ids))
        if any(p.derived for p in pages):
            menu.addAction(theme().icon("perspective", size=16), "Undo perspective fix",
                           lambda: self.undo_perspective(ids))
        menu.addSeparator()
        menu.addAction(theme().icon("rotate_ccw", size=16), "Rotate left", lambda: self.rotate_pages(-90))
        menu.addAction(theme().icon("rotate_cw", size=16), "Rotate right", lambda: self.rotate_pages(90))
        menu.addSeparator()
        menu.addAction(theme().icon("trash", size=16), f"Remove page{plural}", self.remove_selected_pages)
        menu.exec_(position)

    # ======================================================================
    # Exporting
    # ======================================================================

    def _export_pages(self, only_done=False):
        result = []
        for page_id in self.page_list.ordered_ids():
            page = self.pages[page_id]
            if only_done and page.status != Status.DONE:
                continue
            kind, source, index = page.image_source
            result.append(ExportPage(page.label, page.text, kind, source, index,
                                     page.method if page.status == Status.DONE else None,
                                     page.text_pdf, page.total_rotation, page.crop, page.skew))
        return result

    def export(self, kind):
        everything = self._export_pages()
        done = self._export_pages(only_done=True)
        if not done:
            self.show_banner("Nothing has been recognized yet. Click “Recognize” first.", icon="info")
            return
        if len(done) < len(everything):
            missing = len(everything) - len(done)
            text = (f"{missing} of {len(everything)} pages haven't been recognized yet. "
                    + ("They will be included without searchable text." if kind == "pdf"
                       else "Only the recognized pages will be exported."))
            if QMessageBox.question(self, "Export anyway?", text,
                                    QMessageBox.Yes | QMessageBox.Cancel) != QMessageBox.Yes:
                return
        extension, label = {"txt": (".txt", "Text file (*.txt)"),
                            "docx": (".docx", "Word document (*.docx)"),
                            "odt": (".odt", "OpenDocument text (*.odt)"),
                            "md": (".md", "Markdown (*.md)"),
                            "pdf": (".pdf", "PDF document (*.pdf)")}[kind]
        stem = os.path.splitext(self.pages[self.page_list.ordered_ids()[0]].display_name)[0]
        suggested = os.path.join(self.settings.get("ui/last_dir"),
                                 stem + (" (searchable)" if kind == "pdf" else "") + extension)
        path, _ = QFileDialog.getSaveFileName(self, "Export", suggested, label, options=self._dialog_options())
        if not path:
            return
        if not path.lower().endswith(extension):
            path += extension
        self.settings.set("ui/last_dir", os.path.dirname(path))

        if kind == "pdf":
            pages = everything

            def work(progress, token):
                export_searchable_pdf(pages, path, progress, token)
                return path

            self.progress_label.setText("Creating searchable PDF…")
            self.progress_label.show()
            self.progress.show()
            self._run(work, self._exported, lambda m: self._export_failed(m), progress=self._export_progress)
            return
        try:
            if kind == "txt":
                export_text(done, path, self.settings.get("results/page_separators"))
            elif kind == "odt":
                export_odt(done, path)
            elif kind == "md":
                export_markdown(done, path)
            else:
                export_docx(done, path)
        except OSError as error:
            self._export_failed(str(error))
            return
        self._exported(path)

    def _export_progress(self, done, total):
        self.progress.setRange(0, total)
        self.progress.setValue(done)

    def _exported(self, path):
        self.progress.hide()
        self.progress_label.hide()
        self.unsaved = False
        folder = os.path.dirname(path)
        self.show_banner(f"Saved “{os.path.basename(path)}”", "Show in folder",
                         lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(folder)), icon="check")

    def _export_failed(self, message):
        self.progress.hide()
        self.progress_label.hide()
        QMessageBox.warning(self, "Export failed", f"The file could not be saved.\n\n{message}")

    def copy_all_text(self):
        done = self._export_pages(only_done=True)
        if done:
            QApplication.clipboard().setText(join_text(done, self.settings.get("results/page_separators")))
            self.statusBar().showMessage(f"Copied the text of {len(done)} page{'s' if len(done) > 1 else ''}", 4000)

    # ======================================================================
    # Languages, settings, theme
    # ======================================================================

    def _update_languages_ui(self):
        text = summary(self.languages)
        self.language_button.setText(f"{text}  ▾")
        self.language_button.setToolTip("OCR languages: " + ", ".join(display_name(c) for c in self.languages)
                                        + "\nChoose every language that appears in your document.")
        self.empty.set_languages(text)

    def _languages_changed(self, codes):
        self.languages = codes
        self.settings.set("ocr/languages", codes)
        self._update_languages_ui()
        stale = [p.id for p in self.pages.values()
                 if p.status == Status.DONE and p.method == Method.OCR and set(p.languages) != set(codes)]
        if stale:
            self.show_banner(f"Language changed to {summary(codes, 3)}. Recognize "
                             f"{len(stale)} page{'s' if len(stale) > 1 else ''} again with it?",
                             "Recognize again", lambda: self.recognize(stale), icon="globe")

    def manage_languages(self):
        dialog = LanguageManager(self.store, self)
        dialog.languages_installed.connect(self.picker.reload)
        dialog.exec_()
        self.picker.reload()

    def open_settings(self):
        before = {key: self.settings.get(key) for key in OCR_SETTING_KEYS}
        old_theme = self.settings.get("ui/theme")
        dialog = SettingsDialog(self.settings, self.store.has_osd(), self)
        if dialog.exec_() != SettingsDialog.Accepted:
            return
        if self.settings.get("ui/theme") != old_theme:
            self._apply_theme()
        if self.settings.get("ui/restore_session"):
            self._schedule_save()
        else:
            session.clear()  # don't leave document text behind once the user opts out
        self._apply_result_settings()
        self._refresh_current_text()
        self._refresh_all_text()
        changed = any(self.settings.get(key) != value for key, value in before.items())
        done = [p.id for p in self.pages.values() if p.status == Status.DONE]
        if changed and done:
            self.show_banner("Recognition settings changed. Apply them to the pages already recognized?",
                             "Recognize again", lambda: self.recognize(done), icon="settings")

    def _apply_result_settings(self):
        threshold = self.settings.get("results/uncertain_below")
        self.page_list.uncertain_below = threshold
        self.text_panel.threshold = threshold
        self.text_panel.highlight = self.settings.get("results/highlight_uncertain")
        self.page_list.viewport().update()
        self._update_viewer_words(self.pages.get(self.page_list.current_id()))

    def toggle_theme(self):
        self.settings.set("ui/theme", "light" if theme().dark else "dark")
        self._apply_theme()

    def _apply_theme(self):
        theme().apply(self.settings.get("ui/theme"))
        refresh_icons(self)
        refresh_icons(self.picker)
        self.text_panel.find_bar.refresh_icons()
        self.empty.refresh_icons()
        for action in self.actions():
            if action.data():
                action.setIcon(theme().icon(action.data(), size=16))
        self._update_state()
        self.page_list.viewport().update()
        self._refresh_current_text()

    def show_about(self):
        AboutDialog(self.icon_path, self, self.store, self.settings).exec_()

    def report_problem(self):
        QApplication.clipboard().setText(collect_diagnostics(self.store, self.settings))
        open_url(FEEDBACK_URL)
        self.show_banner("Diagnostics were copied to your clipboard. Please paste them into your message "
                         "together with what you did and what went wrong.", icon="info")

    # ======================================================================
    # Helpers
    # ======================================================================

    def show_banner(self, text, action=None, callback=None, icon="info"):
        self._banner_callback = callback
        self.banner.show_message(text, action, icon)

    def _banner_action(self):
        callback, self._banner_callback = self._banner_callback, None
        self.banner.hide()
        if callback:
            callback()

    def _run(self, fn, on_done, on_failed=None, progress=None):
        call = BackgroundCall(fn, self)
        self._calls.add(call)

        def finish():
            self._calls.discard(call)
            call.deleteLater()

        def failed(message):
            self.statusBar().clearMessage()
            (on_failed or (lambda m: self.show_banner(m, icon="warning")))(message)

        call.finished.connect(on_done)
        call.failed.connect(failed)
        for signal in (call.finished, call.failed, call.cancelled):
            signal.connect(lambda *_: finish())
        if progress:
            call.progress.connect(progress)
        call.start()

    def _update_state(self):
        has_pages = bool(self.pages)
        busy = self.jobs.busy
        pending = sum(1 for p in self.pages.values() if p.status in (Status.PENDING, Status.ERROR))
        done = sum(1 for p in self.pages.values() if p.status == Status.DONE)
        button = self.recognize_button
        if busy:
            button.setText(" Stop")
            button.setProperty("iconName", "stop")
            button.setToolTip("Stop recognizing (Ctrl+R)")
        else:
            if pending and pending != len(self.pages):
                button.setText(f" Recognize {pending} page{'s' if pending > 1 else ''}")
            elif pending or not has_pages:
                button.setText(" Recognize")
            else:
                button.setText(" Recognize again")
            button.setProperty("iconName", "scan")
            button.setToolTip("Extract the text from all pages (Ctrl+R)")
        button.setIcon(theme().icon(button.property("iconName"), color=theme().colors["accent_text"], size=18))
        button.setEnabled(has_pages)
        self.act_recognize.setEnabled(has_pages)
        for widget in (self.export_button, self.act_txt, self.act_docx, self.act_odt, self.act_md, self.act_pdf,
                       self.act_xlsx, self.act_csv, self.act_copy_all):
            widget.setEnabled(done > 0)
        self.act_close_all.setEnabled(has_pages)
        self.page_list.setVisible(len(self.pages) > 1)
        current = self.pages.get(self.page_list.current_id())
        name = current.display_name if current else None
        self.setWindowTitle(f"{name} — {APP_NAME}" if name else APP_NAME)

    # ---- session & recent files -------------------------------------------

    def _schedule_save(self):
        if self.settings.get("ui/restore_session"):
            self._save_timer.start()

    def _ordered_pages(self):
        return [self.pages[i] for i in self.page_list.ordered_ids() if i in self.pages]

    def _save_session(self):
        if self._saving:
            self._save_again = True
            return
        pages = self._ordered_pages()
        if not pages:
            session.clear()
            return
        data = session.snapshot(pages)
        before = {entry["id"]: (entry["source"], entry["text_pdf"], entry["derived"]) for entry in data}
        workdir = self.workdir
        self._saving = True

        def saved(moved):
            # Point pages at their copies so the next save doesn't copy again.
            for page_id, changes in moved.items():
                page = self.pages.get(page_id)
                if page is None:
                    continue
                source, layer, derived = before[page_id]
                if "source" in changes and page.source == source:
                    page.source = changes["source"]
                if "derived" in changes and page.derived == derived:
                    page.derived = changes["derived"]
                if "text_pdf" in changes and page.text_pdf == layer:
                    page.text_pdf = changes["text_pdf"]
            finish()

        def finish(*_args):
            self._saving = False
            if self._save_again:
                self._save_again = False
                self._schedule_save()

        def failed(message):
            log.warning("Could not save the session: %s", message)
            finish()

        self._run(lambda _progress, _token: session.save(data, workdir), saved, failed)

    def _save_now(self):
        """Synchronous save, used when quitting."""
        try:
            pages = self._ordered_pages()
            if pages:
                session.save(session.snapshot(pages), self.workdir)
            else:
                session.clear()
        except OSError as error:
            log.warning("Could not save the session: %s", error)

    def _restore_session(self):
        pages = session.load()
        if not pages:
            return
        for page in pages:
            self.pages[page.id] = page
        self.page_list.add_pages(pages)
        for page in pages:
            self.jobs.request_thumbnail(self._job(page))
        self.stack.setCurrentWidget(self.main_split)
        self.page_list.select_id(pages[0].id)
        self.unsaved = any(p.status == Status.DONE for p in pages)
        self._update_state()
        missing = sorted({p.display_name for p in pages if not os.path.exists(p.source)})
        count = len(pages)
        message = f"Restored {count} page{'s' if count != 1 else ''} from last time."
        if missing:
            message += f" Original file{'s' if len(missing) > 1 else ''} not found: {', '.join(missing[:3])}" \
                       " (the text is still here)."
        self.show_banner(message, "Start fresh", self.close_all, icon="refresh")

    def _remember_recent(self, paths):
        if not paths:
            return
        recent = [os.path.abspath(p) for p in paths] + self.settings.get("ui/recent")
        unique = []
        for path in recent:
            if path not in unique:
                unique.append(path)
        self.settings.set("ui/recent", unique[:10])

    def _fill_recent_menu(self):
        self.recent_menu.clear()
        recent = [p for p in self.settings.get("ui/recent") if os.path.exists(p)]
        if not recent:
            action = self.recent_menu.addAction("No recent files")
            action.setEnabled(False)
            return
        for path in recent:
            action = self.recent_menu.addAction(os.path.basename(path.rstrip("/")) or path)
            action.setToolTip(path)
            action.triggered.connect(lambda _checked=False, p=path: self.add_files([p]))
        self.recent_menu.addSeparator()
        self.recent_menu.addAction("Clear list", lambda: self.settings.set("ui/recent", []))

    def _confirm_discard(self, title):
        if not (self.unsaved and any(p.status == Status.DONE and p.text for p in self.pages.values())):
            return True
        answer = QMessageBox.question(self, title, "The recognized text hasn't been exported yet and will be lost.",
                                      QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel)
        return answer == QMessageBox.Discard

    def _restore_geometry(self):
        geometry = self.settings.raw("ui/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            self.resize(min(1280, int(screen.width() * 0.9)), min(820, int(screen.height() * 0.9)))
        for key, splitter in (("ui/main_split", self.main_split), ("ui/content_split", self.content_split)):
            state = self.settings.raw(key)
            if state:
                splitter.restoreState(state)

    def closeEvent(self, event):
        keep = self.settings.get("ui/restore_session")
        if not keep and not self._confirm_discard("Quit PDF2OCR?"):
            event.ignore()
            return
        if keep:
            self._save_timer.stop()
            self._save_now()
        self.settings.set_raw("ui/geometry", self.saveGeometry())
        self.settings.set_raw("ui/main_split", self.main_split.saveState())
        self.settings.set_raw("ui/content_split", self.content_split.saveState())
        for call in list(self._calls):
            call.cancel()
        self.jobs.shutdown()
        event.accept()


def _locale_name():
    from PyQt5.QtCore import QLocale
    return QLocale.system().name()
