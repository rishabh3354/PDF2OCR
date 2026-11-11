# Build environment for the PDF2OCR AppImage.
#
# Ubuntu 22.04 matches the snap (core22), so the AppImage ships the same,
# tested versions of Qt, Tesseract and Poppler. It runs on distributions with
# glibc 2.35 or newer (Ubuntu 22.04+, Debian 12+, Fedora 36+, Mint 21+, ...).
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-pyqt5 \
        poppler-utils \
        tesseract-ocr tesseract-ocr-osd \
        tesseract-ocr-eng tesseract-ocr-deu tesseract-ocr-fra tesseract-ocr-spa \
        tesseract-ocr-ita tesseract-ocr-por tesseract-ocr-nld tesseract-ocr-pol \
        tesseract-ocr-rus tesseract-ocr-ukr tesseract-ocr-tur tesseract-ocr-ara \
        tesseract-ocr-hin tesseract-ocr-chi-sim tesseract-ocr-jpn \
        sane-utils libsane1 sane-airscan \
        dconf-cli \
        ca-certificates patchelf file zsync desktop-file-utils \
    && rm -rf /var/lib/apt/lists/*

# Same Python packages as the snap.
RUN python3 -m pip install --no-cache-dir --target /opt/pydeps "Pillow" "pypdf>=4.0,<8"
