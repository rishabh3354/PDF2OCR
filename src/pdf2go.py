import sys
import time
import webbrowser
import requests
import os
from PyQt5 import QtCore
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox, QGraphicsView, \
    QGraphicsScene, QGraphicsPixmapItem
from PyQt5.QtGui import QPixmap, QMovie, QDesktopServices
from googletrans import Translator
from helper import LANG
from mainwindow import Ui_MainWindow
from pdf2go_threads import Mythread2, Mythread4, Mythread, MovieSplashScreen
from pdftoimagetotext import pdf_to_image
from about_page_new import AboutPageNew
from utils import ExportFile
from extras import BUYMECOFEE, ERROR_MESSAGE
from PyPDF2 import PdfFileReader

QT_DEBUG_PLUGINS = 1
PRODUCT_NAME = 'PDF2GO'
THEME_PATH = '/snap/pdf2go/current/theme/'


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("PDF2OCR")
        self.ui.progressBar.setVisible(False)
        self.make_invisible()
        self.multiple_file_flag = False
        self.ui.lucky_button.setEnabled(False)
        self.ui.lucky_button.setVisible(False)
        self.browse_button_flag = True
        self.click_counter = 1
        self.pdf_browse_file_flag = False
        self.one_time_pdf_extract = True
        self.ui.translate_box.setVisible(False)
        self.ui.converted_text_obj.setVisible(False)
        self.ui.about_button.setEnabled(True)
        self.ui.language_button.setVisible(False)
        self.lock_cache_flag = True
        self.remaining_pdf_page = 0
        self.cached_data_dict = dict()
        self.ui.pdf_show_obj.setAlignment(Qt.AlignCenter)
        self.ui.url_input.textChanged.connect(self.enable_lucky_button)
        self.ui.toolButton.clicked.connect(self.browse_button_clicked)
        self.ui.lucky_button.clicked.connect(self.lucky_button_clicked)
        self.ui.actionOpen_obj.triggered.connect(self.browse_button_clicked)
        # self.ui.about_button.clicked.connect(self.about_me)
        self.ui.export_button.clicked.connect(lambda: self.export(format_type="plain_text"))
        self.ui.next_button.clicked.connect(self.get_next_button_clicked_action)
        self.ui.prev_button.clicked.connect(self.get_prev_button_clicked_action)
        self.ui.translate_box.currentTextChanged.connect(self.translate_data)
        self.ui.hide_text_button.clicked.connect(self.minimize_text_edit)
        self.ui.converted_text_obj.textChanged.connect(self.update_cache_data_in_text_box)
        self.ui.home_buton.clicked.connect(self.press_home_button)
        self.ui.language_button.clicked.connect(self.language_button_click)
        self.ui.theme_button.clicked.connect(self.change_theme)
        self.image_web_url = "/"
        self.single_web_image_file_flag = False
        self.single_browse_image_file_flag = False
        self.ui.zoom_in.clicked.connect(self.zoom_in_functionality)
        self.ui.zoom_out.clicked.connect(self.zoom_out_functionality)
        self.ui.rotate.clicked.connect(self.rotate_functionality)
        self.show_hide_zoom_buttons(hide=True)

        # theme toggle and setup dark theme default.
        self.count = 0  # for theme toggle
        try:
            self.light_theme = THEME_PATH + 'light.qss'
            self.dark_theme = THEME_PATH + 'dark.qss'
            style = open(self.dark_theme, 'r')
        except Exception as e:
            self.light_theme = 'theme/light.qss'
            self.dark_theme = 'theme/dark.qss'
            style = open(self.dark_theme, 'r')
        style = style.read()
        self.setStyleSheet(style)

        # scroll zoom functionality:-
        self._zoom = 0
        self._empty = False
        self._scene = QGraphicsScene(self)
        self._photo = QGraphicsPixmapItem()
        self._scene.addItem(self._photo)
        self.ui.pdf_show_obj.setScene(self._scene)
        self.start_screen_saver()
        self.ui.pdf_show_obj.scale(2, 2)
        self.factor = 1

        #  ======================Your plan functionality starts=============================================

        self.msg = QMessageBox()
        # self.login_ui = LoginPage(login_user=False)
        # self.ui.my_plan_button.clicked.connect(self.my_plan)
        # your_plan_button_connects(self)
        # local_plan_expiry_check
        # ApplicationStartupTask().create_free_trial_offline()
        # include closeEvent function also.
        # include requests, cryptography python package in snapcraft.yaml file.
        # check your check_your_plan function.

        #  ======================About new code=============================================

        self.about_ui = AboutPageNew()
        self.about_ui.setStyleSheet(style)
        self.ui.about_button.clicked.connect(self.show_about_page_new)
        self.about_ui.ui.warlordsoft_button.clicked.connect(self.redirect_to_warlordsoft)
        self.about_ui.ui.donate_button.clicked.connect(self.redirect_to_paypal_donation)
        self.about_ui.ui.rate_button.clicked.connect(self.redirect_to_rate_snapstore)
        self.about_ui.ui.feedback_button.clicked.connect(self.redirect_to_feedback_button)

    def redirect_to_warlordsoft(self):
        warlord_soft_link = "https://warlordsoftwares.com/"
        webbrowser.open(warlord_soft_link)

    def redirect_to_paypal_donation(self):
        paypal_donation_link = "https://www.paypal.com/paypalme/rishabh3354/5"
        webbrowser.open(paypal_donation_link)

    def redirect_to_rate_snapstore(self):
        QDesktopServices.openUrl(QUrl("snap://y2mate"))

    def redirect_to_feedback_button(self):
        feedback_link = "https://warlordsoftwares.com/contact_us/"
        webbrowser.open(feedback_link)

    def zoom_in_functionality(self):

        factor = 1.25
        self._zoom += 1
        if self._zoom > 0:
            self.ui.pdf_show_obj.scale(factor, factor)
        elif self._zoom == 0:
            self.fitInView()
        else:
            self._zoom = 0

    def zoom_out_functionality(self):
        factor = 0.8
        self._zoom -= 1

        if self._zoom > 0:
            self.ui.pdf_show_obj.scale(factor, factor)
        elif self._zoom == 0:
            self.fitInView()
        else:
            self._zoom = 0

    def rotate_functionality(self):
        self.ui.pdf_show_obj.rotate(90)

    def show_hide_zoom_buttons(self, hide=True):
        if hide:
            self.ui.zoom_in.setVisible(False)
            self.ui.zoom_out.setVisible(False)
            self.ui.rotate.setVisible(False)
        else:
            self.ui.zoom_in.setVisible(True)
            self.ui.zoom_out.setVisible(True)
            self.ui.rotate.setVisible(True)

    def change_theme(self):
        theme = self.light_theme
        self.ui.converted_text_obj.setStyleSheet("background-color: rgb(42, 179, 181); padding: 5px; border-radius: "
                                                 "10px;")
        if self.count % 2 != 0:
            theme = self.dark_theme
            self.ui.converted_text_obj.setStyleSheet(
                "color: rgb(238, 238, 236); background-color: rgb(48,48,48);padding: 5px; border-radius: 10px;")
        style = open(theme, 'r')
        style = style.read()
        self.setStyleSheet(style)
        self.about_ui.setStyleSheet(style)
        self.count += 1

    def closeEvent(self, event):
        self.about_ui.hide()

    def hasPhoto(self):
        return not self._empty

    def start_screen_saver(self):
        self.ui.converted_text_obj.setVisible(True)
        self.ui.converted_text_obj.setHtml(BUYMECOFEE)
        self.ui.pdf_show_obj.setVisible(False)
        self.ui.converted_text_obj.setReadOnly(True)

    def fitInView(self, scale=True):
        rect = QtCore.QRectF(self._photo.pixmap().rect())
        if not rect.isNull():
            self.ui.pdf_show_obj.setSceneRect(rect)
            if self.hasPhoto():
                unity = self.ui.pdf_show_obj.transform().mapRect(QtCore.QRectF(0, 0, 1, 1))
                self.ui.pdf_show_obj.scale(1 / unity.width(), 1 / unity.height())
                viewrect = self.ui.pdf_show_obj.viewport().rect()
                scenerect = self.ui.pdf_show_obj.transform().mapRect(rect)
                factor = min(viewrect.width() / scenerect.width(),
                             viewrect.height() / scenerect.height())
                self.ui.pdf_show_obj.scale(factor, factor)
            self._zoom = 0

    def setPhoto(self, pixmap=None):
        self._zoom = 0
        if pixmap and not pixmap.isNull():
            self._empty = False
            self.ui.pdf_show_obj.setDragMode(QGraphicsView.ScrollHandDrag)
            self._photo.setPixmap(pixmap)
        else:
            self._empty = True
            self.ui.pdf_show_obj.setDragMode(QGraphicsView.NoDrag)
            self._photo.setPixmap(QPixmap())
        self.fitInView()

    def setProgressVal(self, value):
        self.one_time_pdf_extract = False
        self.path_list = value
        self.thread2 = Mythread2(self.path_list[0])
        self.thread2.change_value2.connect(self.setProgressVal2)
        self.thread2.start()

    def setProgressVal2(self, value):
        self.ui.pdf_show_obj.setVisible(True)
        self.lock_cache_flag = False
        self.show_hide_zoom_buttons(hide=False)
        if value.isspace():
            value = ERROR_MESSAGE
        if not self.single_web_image_file_flag:
            self.cached_data_dict[self.click_counter] = {"path": self.path_list[self.click_counter - 1],
                                                         "text_data": value,
                                                         "lang": None
                                                         }
        self.thread4 = Mythread4(value)
        self.thread4.change_value4.connect(self.setProgressVal4)
        self.thread4.start()
        if self.single_web_image_file_flag:
            pixmap = QPixmap(self.path)
        else:
            pixmap = QPixmap(self.path_list[self.click_counter - 1])
        self.setPhoto(pixmap)
        self.clear_text_edit_section()
        self.ui.converted_text_obj.setPlainText(value)
        self.ui.language_button.setVisible(True)
        self.ui.toolButton.setEnabled(True)
        self.ui.progressBar.setRange(0, 1)
        self.ui.progressBar.setVisible(False)
        self.ui.url_input.setVisible(True)
        self.ui.converted_text_obj.setReadOnly(False)
        if self.ui.converted_text_obj.toPlainText() != "":
            self.ui.export_button.setEnabled(True)
        if self.single_browse_image_file_flag or self.single_web_image_file_flag:
            pass
        else:
            self.enable_next_prev_button()
        self.ui.hide_text_button.setEnabled(True)
        self.ui.home_buton.setEnabled(True)
        self.ui.converted_text_obj.setVisible(True)
        self.set_file_name_in_url_input()

    def setProgressVal4(self, language):
        try:
            self.set_lang(language)
            self.cached_data_dict[self.click_counter]["lang"] = language
        except Exception as e:
            pass

    def update_cache_data_in_text_box(self):
        try:
            if not self.lock_cache_flag:
                self.cached_data_dict[self.click_counter]["text_data"] = self.ui.converted_text_obj.toPlainText()
        except Exception as e:
            pass

    def make_invisible(self):
        self.ui.prev_button.setVisible(False)
        self.ui.next_button.setVisible(False)
        self.ui.page_no_obj.setVisible(False)

    def browse_button_clicked(self):
        self.click_counter = 1
        self.multiple_file_flag = False
        self.single_web_image_file_flag = False
        self.single_browse_image_file_flag = False
        self.single_web_image_file_flag = False
        self.cached_data_dict.clear()
        self.ui.prev_button.setVisible(False)
        self.ui.next_button.setVisible(False)
        self.ui.page_no_obj.setVisible(False)
        self.ui.toolButton.setEnabled(False)
        self.single_browse_image_file_flag = True
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileNames(self, 'Select Image', "/home/", "Images (*.png *.jpeg *.jpg *.pdf)",
                                                   options=options)
        # fileName, _ = QFileDialog.getOpenFileNames(self, 'Select Image', "/home", "Images (*.png *.jpeg *.jpg *.pdf)")

        if len(fileName) == 0:
            self.ui.toolButton.setEnabled(True)
            return False
        if len(fileName) >= 2:
            self.multiple_file_flag = True
            self.total_pages_count_for_pdf_and_image = len(fileName)
            self.single_browse_image_file_flag = False
        if str(fileName[0]).endswith(".pdf"):
            self.single_browse_image_file_flag = False
            self.pdf_initial_path = fileName[0]
            self.total_pages = self.get_pdf_total_pages(fileName[0])
            self.total_pages_count_for_pdf_and_image = self.total_pages
            if self.total_pages > 1:
                self.pdf_browse_file_flag = True

        self.path = fileName[0]
        self.path_list = fileName
        self.lucky_button_clicked()
        return True

    def start_progress_bar_and_batman_show(self):
        self.ui.url_input.setVisible(False)
        self.ui.lucky_button.setVisible(False)
        self.ui.progressBar.setVisible(True)
        self.ui.progressBar.setRange(0, 0)

    def set_file_name_in_url_input(self):
        if self.single_web_image_file_flag:
            self.ui.url_input.setText(self.image_web_url)
        else:
            self.ui.url_input.setText(self.path_list[self.click_counter - 1])

    def lucky_button_clicked(self):
        # if self.check_your_plan():
        #     return False
        if not MainWindow.check_internet_connection():
            self.msg.about(self, 'No internet connection', "Please check your internet connection!")
            self.browse_button_flag = True
            self.ui.toolButton.setEnabled(True)
            return False

        file_extension_list = [".jpg", ".png", ".jpeg", ".webp", ".tiff", ".bmp", ".svg", ".pdf"]
        self.file_name, self.file_extension = os.path.splitext(self.path)
        if (self.multiple_file_flag or self.pdf_browse_file_flag) and (
                self.ui.prev_button.isEnabled() or self.ui.next_button.isEnabled()):
            try:
                if ".{0}".format(str(self.ui.url_input.text()).split(".")[1]) in [".jpg", ".png", ".jpeg", ".webp",
                                                                                  ".tiff", ".bmp",
                                                                                  ".svg"] and self.file_extension == '.pdf':
                    self.cached_data_dict.clear()
                    self.ui.next_button.setVisible(False)
                    self.ui.prev_button.setVisible(False)
                    self.ui.page_no_obj.setVisible(False)
                    self.click_counter = 1
                    self.pdf_browse_file_flag = False
            except Exception as e:
                pass

        if self.multiple_file_flag or self.pdf_browse_file_flag:
            if self.pdf_browse_file_flag:
                self.ui.page_no_obj.setText(f"Page {self.click_counter} of {self.total_pages}")
            else:
                self.ui.page_no_obj.setText(f"Page {self.click_counter} of {len(self.path_list)}")

        if self.file_extension in file_extension_list:
            if self.path.startswith("http://") or self.path.startswith("https://"):
                self.image_web_url = self.path
                self.ui.lucky_button.setVisible(True)
                try:
                    response = requests.get(self.path)
                    file = open(f"image{self.file_extension}", "wb")
                    file.write(response.content)
                    file.close()
                    self.path = file.name
                    if self.path.endswith(".pdf"):
                        self.total_pages = self.get_pdf_total_pages(self.path)
                        if self.total_pages > 1:
                            self.pdf_browse_file_flag = True
                            self.ui.page_no_obj.setText(f"Page {self.click_counter} of {self.total_pages}")
                            self.enable_next_prev_button()
                    else:
                        self.single_web_image_file_flag = True
                        self.cached_data_dict.clear()

                except Exception as error:
                    self.msg.about(self, 'Error', "Unable to fetch data, please Download the file first!")
                    return False

            if os.path.isfile(self.path):
                self.start_progress_bar_and_batman_show()
                if self.file_extension == ".pdf":
                    self.pdf_page_index = 5
                    self.thread = Mythread(self.path, first_page=1, last_page=5)
                    self.thread.change_value.connect(self.setProgressVal)
                    self.thread.start()

                elif self.file_extension in [".jpg", ".png", ".jpeg", ".webp", ".tiff", ".bmp",
                                             ".svg"] and not self.single_web_image_file_flag:
                    if self.pdf_browse_file_flag and self.click_counter % 2 == 0 and self.click_counter > 2:
                        path_list_buffer = pdf_to_image(self.pdf_initial_path, first_page=self.pdf_page_index + 1,
                                                        last_page=self.pdf_page_index + 2)
                        self.path_list += path_list_buffer
                        self.pdf_page_index += 2

                    self.thread2 = Mythread2(self.path_list[self.click_counter - 1])
                    self.thread2.change_value2.connect(self.setProgressVal2)
                    self.thread2.start()
                else:
                    self.thread2 = Mythread2(self.path)
                    self.thread2.change_value2.connect(self.setProgressVal2)
                    self.thread2.start()
            else:
                self.msg.about(self, 'Error', "Invalid File, Please select Valid Image File")
        else:
            self.msg.about(self, 'Error', "Invalid File, Please select Valid Image File")

    def enable_lucky_button(self):
        str_data = self.ui.url_input.text()
        if str_data != "":
            self.ui.lucky_button.setEnabled(True)
            if str_data.startswith("http://") or str_data.startswith("https://"):
                self.ui.lucky_button.setVisible(True)
                self.browse_button_flag = False
                self.path = self.ui.url_input.text()
        else:
            self.ui.lucky_button.setEnabled(False)

    @staticmethod
    def check_internet_connection():
        try:
            requests.get("http://www.google.com", timeout=5)
            return True
        except (requests.ConnectionError, requests.Timeout):
            return False

    def get_next_button_clicked_action(self):
        if self.multiple_file_flag or self.pdf_browse_file_flag:
            self.ui.prev_button.setEnabled(True)
            self.path = self.path_list[self.click_counter:][0]
            self.click_counter += 1
            if self.check_cached_data():
                self.get_cached_values()
            else:
                self.lucky_button_clicked()
                self.ui.next_button.setEnabled(False)
            try:
                self.total_pages_count_for_pdf_and_image = self.total_pages
            except Exception as e:
                self.total_pages_count_for_pdf_and_image = self.total_pages_count_for_pdf_and_image
                pass
            try:
                self.ui.page_no_obj.setText(f"Page {self.click_counter} of {self.total_pages_count_for_pdf_and_image}")
                if self.click_counter == len(self.path_list):
                    self.ui.next_button.setEnabled(False)
                self.set_file_name_in_url_input()
            except Exception as e:
                pass

    def get_prev_button_clicked_action(self):
        if self.multiple_file_flag or self.pdf_browse_file_flag:
            self.path = self.path_list[:-self.click_counter + 1][len(self.path_list[:-self.click_counter + 1]) - 1]
            self.click_counter -= 1
            if self.check_cached_data():
                self.get_cached_values()
                self.ui.next_button.setEnabled(True)
            else:
                self.lucky_button_clicked()
            try:
                self.total_pages_count_for_pdf_and_image = self.total_pages
            except Exception as e:
                self.total_pages_count_for_pdf_and_image = self.total_pages_count_for_pdf_and_image
                pass
            try:
                self.ui.page_no_obj.setText(f"Page {self.click_counter} of {self.total_pages_count_for_pdf_and_image}")
                if self.click_counter == 1:
                    self.ui.prev_button.setEnabled(False)
                    self.ui.next_button.setEnabled(True)
                self.set_file_name_in_url_input()
            except Exception as e:
                pass

    def check_cached_data(self):
        return True if self.cached_data_dict.get(self.click_counter) else False

    def get_cached_values(self):
        cache_data = self.cached_data_dict[self.click_counter]
        path = cache_data["path"]
        text_data = cache_data["text_data"]
        lang = cache_data["lang"]

        pixmap = QPixmap(path)
        self.setPhoto(pixmap)
        self.ui.converted_text_obj.setPlainText(text_data)
        self.ui.progressBar.setRange(0, 1)
        self.ui.progressBar.setVisible(False)
        self.ui.url_input.setVisible(True)
        try:
            self.ui.translate_box.setCurrentText(LANG[str(lang).lower()])
        except Exception as e:
            pass

    def enable_next_prev_button(self):
        if self.multiple_file_flag or self.pdf_browse_file_flag:
            self.ui.next_button.setVisible(True)
            self.ui.prev_button.setVisible(True)
            self.ui.page_no_obj.setVisible(True)
        try:
            if self.click_counter == len(self.path_list):
                self.ui.next_button.setEnabled(False)
            else:
                self.ui.next_button.setEnabled(True)
        except Exception as e:
            pass

    def get_pdf_total_pages(self, path):
        pdf = PdfFileReader(open(path, 'rb'))
        return pdf.getNumPages()

    def export(self, format_type):
        types = {"pdf": "PDF files (*.pdf)", "plain_text": "Plain Text (*.txt)", "mp3": "Mp3 (*.mp3)"}
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_path = QFileDialog.getSaveFileName(self, self.tr("Export document to PDF"),
                                                "/home/Documents/Pdf2go",
                                                self.tr(types[format_type]), options=options)[0]
        data = str(self.ui.converted_text_obj.toPlainText()).strip("\f")
        if file_path == '':
            return False

        if data and data != "":
            ExportFile(data, file_path, format_type=format_type, lang=self.to_trans).export()
            self.msg.about(self, 'Success', "Export Successfully!")
        else:
            self.msg.warning(self, "Failed", "Nothing to export!")

    def translate_data(self):
        try:
            trans = Translator()
            current_lang = self.ui.translate_box.currentText()
            raw_str = self.ui.converted_text_obj.toPlainText()
            self.to_trans = list(LANG.keys())[list(LANG.values()).index(current_lang)]
            trans_text = trans.translate(raw_str, dest=self.to_trans).text
            self.ui.converted_text_obj.setPlainText(str(trans_text))
            self.ui.translate_box.setCurrentText(self.to_trans)
            self.cached_data_dict[self.click_counter] = {"path": self.path_list[self.click_counter - 1],
                                                         "text_data": trans_text,
                                                         "lang": self.to_trans
                                                         }
        except Exception as e:
            pass

    def set_items_in_combobox(self):
        self.ui.translate_box.setEnabled(True)
        lang_list = LANG.values()
        self.ui.translate_box.addItems(lang_list)
        trans = Translator()
        self.current_lang = trans.detect(self.ui.converted_text_obj.toPlainText()).lang
        self.ui.translate_box.setCurrentText(LANG[str(self.current_lang).lower()])

    def set_lang(self, language):
        self.ui.translate_box.setEnabled(True)
        lang_list = LANG.values()
        self.ui.translate_box.addItems(lang_list)
        self.ui.translate_box.setCurrentText(LANG[str(language).lower()])

    def minimize_text_edit(self):
        if self.ui.pdf_show_obj.isVisible():
            self.ui.pdf_show_obj.setVisible(False)
            self.show_hide_zoom_buttons(hide=True)
        else:
            self.ui.pdf_show_obj.setVisible(True)
            self.show_hide_zoom_buttons(hide=False)

    def press_home_button(self):
        self.show_hide_zoom_buttons(hide=True)
        self.ui.lucky_button.setVisible(False)
        self.ui.export_button.setEnabled(False)
        self.ui.hide_text_button.setEnabled(False)
        self.ui.translate_box.setVisible(False)
        self.ui.next_button.setVisible(False)
        self.ui.prev_button.setVisible(False)
        self.ui.page_no_obj.setVisible(False)
        self.ui.converted_text_obj.setVisible(False)
        self.ui.language_button.setVisible(False)
        self.browse_button_flag = True
        self.ui.url_input.clear()
        self.cached_data_dict.clear()
        self.ui.toolButton.setEnabled(True)
        if not self.ui.pdf_show_obj.isVisible():
            self.ui.pdf_show_obj.setVisible(True)
        self.start_screen_saver()
        self.fitInView()
        try:
            self.ui.progressBar.setVisible(False)
            self.ui.url_input.setVisible(True)
            self.thread2.quit()
            self.thread.quit()
            self.thread3.quit()
        except Exception as e:
            pass

    def clear_text_edit_section(self):
        if self.ui.converted_text_obj.isVisible():
            self.ui.converted_text_obj.clear()
            self.ui.pdf_show_obj.setVisible(True)
            self.ui.converted_text_obj.setVisible(False)
        else:
            self.ui.pdf_show_obj.setVisible(True)
            self.ui.converted_text_obj.clear()

    def language_button_click(self):
        if not self.ui.translate_box.isVisible():
            self.ui.translate_box.setVisible(True)
            if not self.ui.converted_text_obj.isVisible():
                self.ui.converted_text_obj.setVisible(True)
        else:
            self.ui.translate_box.setVisible(False)
            self.minimize_text_edit()

    # About code starts: ==========================

    def show_about_page_new(self):
        self.about_ui.show()

    # ================Login code starts=======================================

    # def my_plan(self):
    #     self.login_ui.show()
    #     token = check_for_local_token()
    #     if token not in [None, ""]:
    #         user_plan_data = get_user_data_from_local()
    #         if user_plan_data:
    #             user_plan_data = convert_date_str_for_user_data(user_plan_data)
    #             self.logged_in_user_plan_page(user_plan_data)
    #         else:
    #             user_plan_data = dict()
    #             user_plan_data['plan'] = "N/A"
    #             user_plan_data['expiry_date'] = "N/A"
    #             user_plan_data['created_on'] = "N/A"
    #             user_plan_data['email'] = "N/A"
    #             user_plan_data['product'] = PRODUCT_NAME
    #             self.logged_in_user_plan_page(user_plan_data)
    #     else:
    #         user_plan_data = get_user_data_from_local()
    #         if user_plan_data:
    #             user_plan_data = convert_date_str_for_user_data(user_plan_data)
    #             self.logged_out_user_plan_page(user_plan_data)

    # def check_your_plan(self):
        # if ApplicationStartupTask().is_expired_product():
        #     self.msg.setIcon(QMessageBox.Information)
        #     self.msg.setText("Plan Expired!")
        #     self.msg.setInformativeText("Your trial period has expired. Please purchase a plan (75% OFF)")
        #     self.msg.setWindowTitle(PRODUCT_NAME)
        #     month_name = datetime.datetime.now().date().strftime("%B")
        #     self.msg.setDetailedText(f"In {month_name} month we are giving bumpher"
        #                              f" discount of 75% OFF. Valid for limited period only.\nHURRY UP !!")
        #     self.msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Close)
        #     purchase_button = self.msg.button(QMessageBox.Ok)
        #     purchase_button.setText('Purchase Now')
        #     self.msg.exec_()
        #     self.ui.toolButton.setEnabled(True)
        #     if self.msg.clickedButton() == purchase_button:
        #         self.my_plan()
        #         return True
        #     else:
        #         return True
        # else:
        #     return False

    # def logged_in_user_plan_page(self, user_plan_data):
    #     self.login_ui.ui.product_name.setText(PRODUCT_NAME)
    #     self.login_ui.ui.purchase_plan_obj_2.setText(user_plan_data.get("plan", "N/A"))
    #     if notify_for_expiry(user_plan_data.get("expiry_date")):
    #         self.login_ui.ui.refresh_error.setText("YOUR PLAN HAS EXPIRED, PLEASE BUY A PLAN")
    #     self.login_ui.ui.expire_on_obj_2.setText(user_plan_data.get("expiry_date", "N/A"))
    #     self.login_ui.ui.activation_date_obj_2.setText(user_plan_data.get("created_on", "N/A"))
    #     self.login_ui.ui.hello_user_email_obj_2.setText(f"Welcome {user_plan_data.get('email', 'How are you today')}")
    #     self.login_ui.ui.log_out_button_obj_2.setVisible(True)
    #     self.login_ui.ui.login_from_your_plan.setVisible(False)
    #
    # def logged_out_user_plan_page(self, user_plan_data):
    #     self.login_ui.ui.product_name.setText(PRODUCT_NAME)
    #     self.login_ui.ui.purchase_plan_obj_2.setText(user_plan_data.get("plan", "N/A"))
    #     if notify_for_expiry(user_plan_data.get("expiry_date")):
    #         self.login_ui.ui.refresh_error.setText("YOUR PLAN HAS EXPIRED, PLEASE BUY A PLAN")
    #     self.login_ui.ui.expire_on_obj_2.setText(user_plan_data.get("expiry_date", "N/A"))
    #     self.login_ui.ui.activation_date_obj_2.setText(user_plan_data.get("created_on", "N/A"))
    #     self.login_ui.ui.hello_user_email_obj_2.setText('Please Signin/Register to see your updated plan')
    #     self.login_ui.ui.log_out_button_obj_2.setVisible(False)
    #
    # def logout_function(self):
    #     self.login_ui.ui.product_name.setText(PRODUCT_NAME)
    #     self.login_ui.ui.purchase_plan_obj_2.setText("N/A")
    #     self.login_ui.ui.expire_on_obj_2.setText("N/A")
    #     self.login_ui.ui.activation_date_obj_2.setText("N/A")
    #     self.login_ui.ui.hello_user_email_obj_2.setText("Please Signin/Register to see your plan details.")
    #     self.login_ui.ui.log_out_button_obj_2.setVisible(False)
    #     self.login_ui.ui.login_from_your_plan.setVisible(True)
    #     self.login_ui.ui.purchase_now_button_2.setVisible(True)
    #     delete_user_data_from_local()
    #
    # def sign_in_user(self):
    #     for i in range(self.login_ui.ui.register_gridLayout_2.count() - 1, -1, -1):
    #         items = self.login_ui.ui.register_gridLayout_2.itemAt(i).widget()
    #         if items:
    #             items.setVisible(False)
    #
    #     for i in range(self.login_ui.ui.your_plan_gridLayout.count() - 1, -1, -1):
    #         items = self.login_ui.ui.your_plan_gridLayout.itemAt(i).widget()
    #         if items:
    #             items.setVisible(False)
    #
    #     for i in range(self.login_ui.ui.login_gridLayout.count() - 1, -1, -1):
    #         items = self.login_ui.ui.login_gridLayout.itemAt(i).widget()
    #         if items:
    #             if items.objectName() != "login_progressBar_2":
    #                 items.setVisible(True)
    #
    #     self.login_ui.ui.home_button.setEnabled(True)
    #
    # def purchase_now(self):
    #     if self.login_ui.ui.log_out_button_obj_2.isVisible():
    #         token = check_for_local_token()
    #         warlord_soft_link = f"https://warlordsoftwares.com/warlord_soft/subscription/?product={PRODUCT_NAME}&token={token} "
    #         webbrowser.open(warlord_soft_link)
    #     else:
    #         for i in range(self.login_ui.ui.your_plan_gridLayout.count() - 1, -1, -1):
    #             items = self.login_ui.ui.your_plan_gridLayout.itemAt(i).widget()
    #             if items:
    #                 items.setVisible(False)
    #         self.login_ui.ui.home_button.setEnabled(True)
    #
    #         for i in range(self.login_ui.ui.login_gridLayout.count() - 1, -1, -1):
    #             items = self.login_ui.ui.login_gridLayout.itemAt(i).widget()
    #             if items:
    #                 items.setVisible(False)
    #
    #         for i in range(self.login_ui.ui.register_gridLayout_2.count() - 1, -1, -1):
    #             items = self.login_ui.ui.register_gridLayout_2.itemAt(i).widget()
    #             if items:
    #                 if items.objectName() != "register_progressBar":
    #                     items.setVisible(True)
    #
    # def refresh_button_function(self):
    #     if self.login_ui.ui.log_out_button_obj_2.isVisible():
    #         self.login_ui.ui.refresh_error.clear()
    #         self.login_ui.ui.login_progressBar_2.setRange(0, 0)
    #         self.login_ui.ui.login_progressBar_2.setVisible(True)
    #         self.refresh_thread = RefreshButtonThread()
    #         self.refresh_thread.change_value_refresh.connect(self.after_refresh)
    #         self.refresh_thread.start()
    #     else:
    #         message = self.login_ui.ui.refresh_error.text()
    #         if message != 'Please do Signin first':
    #             self.login_ui.ui.refresh_error.setText("Please do Signin first")
    #         else:
    #             self.login_ui.ui.refresh_error.clear()
    #
    # def after_refresh(self, token_str):
    #     token_data = {'status': True, 'token': token_str}
    #     self.after_login_step_from_signin(token_data)
    #     self.login_ui.ui.login_progressBar_2.setRange(0, 1)
    #     self.login_ui.ui.login_progressBar_2.setVisible(False)
    #
    # def show_register_page(self):
    #     for i in range(self.login_ui.ui.register_gridLayout_2.count() - 1, -1, -1):
    #         items = self.login_ui.ui.register_gridLayout_2.itemAt(i).widget()
    #         if items:
    #             if items.objectName() != "register_progressBar":
    #                 items.setVisible(True)
    #
    #     for i in range(self.login_ui.ui.your_plan_gridLayout.count() - 1, -1, -1):
    #         items = self.login_ui.ui.your_plan_gridLayout.itemAt(i).widget()
    #         if items:
    #             items.setVisible(False)
    #
    #     for i in range(self.login_ui.ui.login_gridLayout.count() - 1, -1, -1):
    #         items = self.login_ui.ui.login_gridLayout.itemAt(i).widget()
    #         if items:
    #             items.setVisible(False)
    #
    #     self.login_ui.ui.home_button.setEnabled(True)
    #
    # def register_user(self):
    #     data = dict()
    #     data["email"] = str(self.login_ui.ui.register_email_id_obj.text()).strip()
    #     data["password"] = str(self.login_ui.ui.register_password_obj.text()).strip()
    #     data["re_password"] = str(self.login_ui.ui.register_re_password_obj.text()).strip()
    #
    #     self.login_ui.ui.register_progressBar.setRange(0, 0)
    #     self.login_ui.ui.register_progressBar.setVisible(True)
    #
    #     self.login_thread = SignUpThread(data)
    #     self.login_thread.change_value_signup.connect(self.after_signup_step)
    #     self.login_thread.start()
    #
    # def after_signup_step(self, data):
    #     if data["status"]:
    #         self.login_thread = LoggingInThread(data)
    #         self.login_thread.change_value_login.connect(self.after_login_step)
    #         self.login_thread.start()
    #     else:
    #         error_message = data.get("message")
    #         if error_message:
    #             self.login_ui.ui.register_error_message.setText(error_message)
    #         else:
    #             self.login_ui.ui.register_error_message.setText("Internal Server Error")
    #         self.login_ui.ui.register_progressBar.setRange(0, 1)
    #         self.login_ui.ui.register_progressBar.setVisible(False)
    #
    # def after_login_step(self, data):
    #     if data["status"]:
    #         self.login_ui.ui.register_progressBar.setRange(0, 1)
    #         self.login_ui.ui.register_progressBar.setVisible(False)
    #         self.show_your_plan_page(data)
    #         token = check_for_local_token()
    #         warlord_soft_link = f"https://warlordsoftwares.com/warlord_soft/subscription/?product={PRODUCT_NAME}&token={token} "
    #         webbrowser.open(warlord_soft_link)
    #     else:
    #         error_message = data.get("message")
    #         if error_message:
    #             self.login_ui.ui.register_error_message.setText(error_message)
    #         else:
    #             self.login_ui.ui.register_error_message.setText("Internal Server Error")
    #         self.login_ui.ui.register_progressBar.setRange(0, 1)
    #         self.login_ui.ui.register_progressBar.setVisible(False)
    #     self.login_ui.ui.home_button.setEnabled(False)
    #     self.login_ui.ui.login_from_your_plan.setVisible(False)
    #
    # def after_login_step_from_signin(self, data):
    #     if data["status"]:
    #         self.login_ui.ui.login_progressBar_2.setRange(0, 1)
    #         self.login_ui.ui.login_progressBar_2.setVisible(False)
    #         self.show_your_plan_page(data, from_signin=True)
    #     else:
    #         error_message = data.get("message")
    #         if error_message:
    #             self.login_ui.ui.login_error_message_2.setText(error_message)
    #         else:
    #             self.login_ui.ui.login_error_message_2.setText("Internal Server Error")
    #         self.login_ui.ui.login_progressBar_2.setRange(0, 1)
    #         self.login_ui.ui.login_progressBar_2.setVisible(False)
    #     self.login_ui.ui.home_button.setEnabled(False)
    #
    # def show_home_page(self):
    #     for i in range(self.login_ui.ui.register_gridLayout_2.count() - 1, -1, -1):
    #         items = self.login_ui.ui.register_gridLayout_2.itemAt(i).widget()
    #         if items:
    #             items.setVisible(False)
    #     for i in range(self.login_ui.ui.login_gridLayout.count() - 1, -1, -1):
    #         items = self.login_ui.ui.login_gridLayout.itemAt(i).widget()
    #         if items:
    #             items.setVisible(False)
    #
    #     for i in range(self.login_ui.ui.your_plan_gridLayout.count() - 1, -1, -1):
    #         items = self.login_ui.ui.your_plan_gridLayout.itemAt(i).widget()
    #         if items:
    #             if items.objectName() != "register_progressBar":
    #                 items.setVisible(True)
    #
    #     self.login_ui.resize(450, 450)
    #     self.my_plan()
    #
    # def show_your_plan_page(self, data, from_signin=False):
    #     for i in range(self.login_ui.ui.register_gridLayout_2.count() - 1, -1, -1):
    #         items = self.login_ui.ui.register_gridLayout_2.itemAt(i).widget()
    #         if items:
    #             items.setVisible(False)
    #     for i in range(self.login_ui.ui.login_gridLayout.count() - 1, -1, -1):
    #         items = self.login_ui.ui.login_gridLayout.itemAt(i).widget()
    #         if items:
    #             items.setVisible(False)
    #
    #     for i in range(self.login_ui.ui.your_plan_gridLayout.count() - 1, -1, -1):
    #         items = self.login_ui.ui.your_plan_gridLayout.itemAt(i).widget()
    #         if items:
    #             if items.objectName() != "register_progressBar":
    #                 items.setVisible(True)
    #
    #     SignInUpdatePlan(PRODUCT_NAME, data.get("token")).update_local_expiry_and_client_data()
    #     user_plan_data = get_user_data_from_local()
    #     if user_plan_data:
    #         user_plan_data = convert_date_str_for_user_data(user_plan_data)
    #         self.login_ui.ui.purchase_plan_obj_2.setText(user_plan_data.get("plan", "N/A"))
    #         if user_plan_data.get("plan", "N/A") == 'Life Time Free Plan':
    #             self.login_ui.ui.purchase_now_button_2.setVisible(False)
    #         self.login_ui.ui.product_name.setText(str(user_plan_data.get("product", PRODUCT_NAME)).upper())
    #         self.login_ui.ui.expire_on_obj_2.setText(user_plan_data.get("expiry_date", "N/A"))
    #         self.login_ui.ui.activation_date_obj_2.setText(user_plan_data.get("created_on", "N/A"))
    #         self.login_ui.ui.hello_user_email_obj_2.setText(
    #             f"Welcome {user_plan_data.get('email', 'How are you today')}")
    #         if from_signin:
    #             self.login_ui.ui.login_from_your_plan.setVisible(False)
    #
    # def validate_password(self):
    #     if self.login_ui.ui.register_re_password_obj.text() not in [None, ""] or \
    #             self.login_ui.ui.register_password_obj.text() not in [None, ""]:
    #         if not len(self.login_ui.ui.register_password_obj.text()) > 3:
    #             self.login_ui.ui.register_error_message.setText("Password length is short!")
    #             self.login_ui.ui.register_button_obj.setEnabled(False)
    #         else:
    #             if self.login_ui.ui.register_password_obj.text() != self.login_ui.ui.register_re_password_obj.text():
    #                 self.login_ui.ui.register_error_message.setText("Password does not match!")
    #                 self.login_ui.ui.register_button_obj.setEnabled(False)
    #             else:
    #                 self.login_ui.ui.register_error_message.clear()
    #                 self.login_ui.ui.register_button_obj.setEnabled(True)
    #                 self.validate_email()
    #
    # def validate_email(self):
    #     if self.login_ui.ui.register_email_id_obj.text() not in [None, ""]:
    #         regex = '^[a-z0-9A-Z]+[\._]?[a-z0-9A-Z]+[@]\w+-?\w+[.]\w{2,3}$'
    #         if re.search(regex, self.login_ui.ui.register_email_id_obj.text()):
    #             self.login_ui.ui.register_error_message.clear()
    #             self.login_ui.ui.register_button_obj.setEnabled(True)
    #         else:
    #             self.login_ui.ui.register_error_message.setText("Enter valid email address!")
    #             self.login_ui.ui.register_button_obj.setEnabled(False)
    #
    # def validate_login_email(self):
    #     if self.login_ui.ui.login_email_obj.text() not in [None, ""]:
    #         regex = '^[a-z0-9A-Z]+[\._]?[a-z0-9A-Z]+[@]\w+-?\w+[.]\w{2,3}$'
    #         if re.search(regex, self.login_ui.ui.login_email_obj.text()):
    #             self.login_ui.ui.login_error_message_2.clear()
    #             if self.login_ui.ui.login_password_obj.text() != "":
    #                 self.login_ui.ui.login_from_login.setEnabled(True)
    #         else:
    #             self.login_ui.ui.login_error_message_2.setText("Enter valid email address!")
    #             self.login_ui.ui.login_from_login.setEnabled(False)
    #
    # def validate_login_password(self):
    #     if self.login_ui.ui.login_password_obj.text() != "":
    #         if self.login_ui.ui.login_email_obj.text() not in [None, ""]:
    #             regex = '^[a-z0-9A-Z]+[\._]?[a-z0-9A-Z]+[@]\w+-?\w+[.]\w{2,3}$'
    #             if re.search(regex, self.login_ui.ui.login_email_obj.text()):
    #                 self.login_ui.ui.login_error_message_2.clear()
    #                 self.login_ui.ui.login_from_login.setEnabled(True)
    #     else:
    #         self.login_ui.ui.login_error_message_2.setText("Password cannot be empty !")
    #         self.login_ui.ui.login_from_login.setEnabled(False)
    #
    # def after_login_show_your_plan(self):
    #     self.login_ui.ui.login_progressBar_2.setRange(0, 0)
    #     self.login_ui.ui.login_progressBar_2.setVisible(True)
    #     data = {"data": {"email": str(self.login_ui.ui.login_email_obj.text()).strip(),
    #                      "password": str(self.login_ui.ui.login_password_obj.text()).strip()}}
    #     self.login_thread = LoggingInThread(data)
    #     self.login_thread.change_value_login.connect(self.after_login_step_from_signin)
    #     self.login_thread.start()
    #
    # def redirect_to_warlord_softwares(self):
    #     warlord_soft_link = "https://warlordsoftwares.com/"
    #     webbrowser.open(warlord_soft_link)

    #  ==============================Login code ends==================================================


if __name__ == "__main__":
    app = QApplication(sys.argv)
    movie = QMovie(":/myresource/resource/pdf2go_startup_screen.gif")
    splash = MovieSplashScreen(movie)
    splash.show()
    start = time.time()
    while movie.state() == QMovie.Running and time.time() < start + 1:
        app.processEvents()
    window = MainWindow()
    window.show()
    splash.finish(window)
    sys.exit(app.exec_())
