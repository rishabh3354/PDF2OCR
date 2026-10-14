"""Background work: OCR batches, page rendering and one-off tasks.

Workers run in QThreadPools and only ever emit signals; all bookkeeping and
every change to Page objects happens on the UI thread in the connected slots.
"""

import logging
import os

from PyQt5.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from .engine import PREVIEW_EDGE, recognize, render_preview
from .tools import CancelToken, Cancelled, ToolError

log = logging.getLogger(__name__)

THUMBNAIL_EDGE = 260
PRIORITY_PREVIEW = 10


class _Task(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self._fn = fn
        self.setAutoDelete(True)

    def run(self):
        try:
            self._fn()
        except RuntimeError as error:
            # The receiver was destroyed while we worked (window closed); nothing to report to.
            if "has been deleted" not in str(error):
                raise


def _describe(error):
    if isinstance(error, ToolError):
        return str(error)
    log.exception("Unexpected error in background task")
    return f"Unexpected error: {error}"


class JobManager(QObject):
    ocr_started = pyqtSignal(int)
    ocr_finished = pyqtSignal(int, object)
    ocr_failed = pyqtSignal(int, str)
    ocr_cancelled = pyqtSignal(int)
    batch_progress = pyqtSignal(int, int)
    batch_finished = pyqtSignal(bool)
    preview_ready = pyqtSignal(int, str)
    thumbnail_ready = pyqtSignal(int, str)

    _ocr_done = pyqtSignal(int, object, str)
    _render_done = pyqtSignal(int, str, bool)

    def __init__(self, workdir, parent=None):
        super().__init__(parent)
        self.workdir = workdir
        self.ocr_pool = QThreadPool(self)
        self.render_pool = QThreadPool(self)
        self.render_pool.setMaxThreadCount(2)
        self._token = None
        self._total = 0
        self._done = 0
        self._rendering = set()
        self._ocr_done.connect(self._on_ocr_done)
        self._render_done.connect(self._on_render_done)

    # ---- OCR -------------------------------------------------------------

    @property
    def busy(self):
        return self._token is not None

    def recognize(self, jobs, options, parallel):
        if not jobs:
            return
        if self._token is None:
            self._token = CancelToken()
            self._total = self._done = 0
        self.ocr_pool.setMaxThreadCount(max(1, parallel))
        self._total += len(jobs)
        token = self._token
        for job in jobs:
            self.ocr_pool.start(_Task(lambda job=job: self._run_ocr(job, options, token)))
        self.batch_progress.emit(self._done, self._total)

    def cancel(self):
        if self._token:
            self._token.cancel()

    def _run_ocr(self, job, options, token):
        if token.cancelled:
            self._ocr_done.emit(job.page_id, None, "")
            return
        self.ocr_started.emit(job.page_id)
        try:
            result = recognize(job, options, self.workdir, token)
            self._ocr_done.emit(job.page_id, result, "")
        except Cancelled:
            self._ocr_done.emit(job.page_id, None, "")
        except Exception as error:  # noqa: BLE001 - reported to the user
            if token.cancelled:
                self._ocr_done.emit(job.page_id, None, "")
            else:
                self._ocr_done.emit(job.page_id, None, _describe(error))

    def _on_ocr_done(self, page_id, result, error):
        if result is not None:
            self.ocr_finished.emit(page_id, result)
        elif error:
            self.ocr_failed.emit(page_id, error)
        else:
            self.ocr_cancelled.emit(page_id)
        self._done += 1
        self.batch_progress.emit(self._done, self._total)
        if self._done >= self._total:
            cancelled = self._token.cancelled
            self._token = None
            self.batch_finished.emit(cancelled)

    # ---- Rendering -------------------------------------------------------

    def request_preview(self, job):
        self._render(job, preview=True)

    def request_thumbnail(self, job):
        self._render(job, preview=False)

    def _render(self, job, preview):
        key = (job.page_id, preview)
        if key in self._rendering:
            return
        self._rendering.add(key)
        kind = "preview" if preview else "thumb"
        base = os.path.join(self.workdir, f"{kind}-{job.page_id}")
        edge = PREVIEW_EDGE if preview else THUMBNAIL_EDGE

        def work():
            try:
                path = render_preview(job, base, edge)
            except Exception as error:  # noqa: BLE001
                log.warning("Could not render page %s: %s", job.page_id, error)
                path = ""
            self._render_done.emit(job.page_id, path, preview)

        self.render_pool.start(_Task(work), PRIORITY_PREVIEW if preview else 0)

    def _on_render_done(self, page_id, path, preview):
        self._rendering.discard((page_id, preview))
        (self.preview_ready if preview else self.thumbnail_ready).emit(page_id, path)

    def shutdown(self):
        self.cancel()
        self.ocr_pool.clear()
        self.render_pool.clear()
        self.ocr_pool.waitForDone(3000)
        self.render_pool.waitForDone(3000)


class BackgroundCall(QObject):
    """Run fn(progress, token) in a worker thread and report back on the UI thread.

    fn receives a progress(done, total) callback and a CancelToken.
    """

    finished = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()
    progress = pyqtSignal(int, int)

    _pool = None

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn
        self.token = CancelToken()

    def start(self):
        if BackgroundCall._pool is None:
            BackgroundCall._pool = QThreadPool()
            BackgroundCall._pool.setMaxThreadCount(3)
        BackgroundCall._pool.start(_Task(self._run))
        return self

    def cancel(self):
        self.token.cancel()

    def _run(self):
        try:
            result = self._fn(self.progress.emit, self.token)
        except Cancelled:
            self.cancelled.emit()
        except Exception as error:  # noqa: BLE001
            if self.token.cancelled:
                self.cancelled.emit()
            else:
                self.failed.emit(_describe(error))
        else:
            self.finished.emit(result)
