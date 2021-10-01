from PyQt5.QtWidgets import QWidget
from about_page import Ui_Dialog


class AboutPageNew(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle("About")
