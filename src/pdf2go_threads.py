from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QPainter, QPixmap
from PyQt5.QtWidgets import QSplashScreen
from helper import detect_lang
from pdftoimagetotext import pdf_to_image


class MovieSplashScreen(QSplashScreen):

    def __init__(self, movie, parent=None):
        movie.jumpToFrame(0)
        pixmap = QPixmap(movie.frameRect().size())

        QSplashScreen.__init__(self, pixmap)
        self.movie = movie
        self.movie.frameChanged.connect(self.repaint)

    def showEvent(self, event):
        self.movie.start()

    def hideEvent(self, event):
        self.movie.stop()

    def paintEvent(self, event):
        painter = QPainter(self)
        pixmap = self.movie.currentPixmap()
        self.setMask(pixmap.mask())
        painter.drawPixmap(0, 0, pixmap)

    def sizeHint(self):
        return self.movie.scaledSize()


class Mythread(QtCore.QThread):
    change_value = pyqtSignal(list)

    def __init__(self, path, first_page, last_page, parent=None):
        super(Mythread, self).__init__(parent)
        self.path = path
        self.first_page = first_page
        self.last_page = last_page

    def run(self):
        image_path_all = pdf_to_image(self.path, self.first_page, self.last_page)
        self.change_value.emit(image_path_all)


class Mythread2(QtCore.QThread):
    change_value2 = pyqtSignal(str)

    def __init__(self, path, parent=None):
        super(Mythread2, self).__init__(parent)
        self.path = path

    def run(self):
        import extract
        self.extracted_text = extract.return_string(self.path)
        self.change_value2.emit(self.extracted_text)


class Mythread4(QtCore.QThread):
    change_value4 = pyqtSignal(str)

    def __init__(self, text, parent=None):
        super(Mythread4, self).__init__(parent)
        self.text = text

    def run(self):
        try:
            self.lang = detect_lang(self.text)
        except Exception as e:
            self.lang = "en"
        self.change_value4.emit(self.lang)
