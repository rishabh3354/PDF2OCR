import pytesseract
from PIL import Image
from pdf2go import ERROR_MESSAGE


def return_string(path):
    try:
        img = Image.open(path)
        pytesseract.pytesseract.tesseract_cmd = r'/snap/pdf2go/current/usr/bin/tesseract'
        # pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'
        result = pytesseract.image_to_string(img, timeout=30)
    except Exception as e:
        result = ERROR_MESSAGE
    return result





