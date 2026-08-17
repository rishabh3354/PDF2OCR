# PDF2OCR — Extract Text from Scanned PDFs and Images on Linux (Tesseract OCR)

**PDF2OCR turns scanned PDFs, photos and screenshots into editable text using Tesseract OCR.** Open a file from your computer or straight from a URL, page through multi-page documents, translate the extracted text, and export it as plain text. OCR runs locally on your machine.

**Open source under the MIT licence** — the full PyQt5 application source is in [`src/`](src).

<p align="center">
  <a href="https://snapcraft.io/pdf2go"><img src="https://img.shields.io/snapcraft/v/pdf2go/latest/stable?style=for-the-badge&label=Snap%20Store&color=E95420" alt="Snap Store version"></a>
  <a href="src/LICENSE"><img src="https://img.shields.io/badge/License-MIT-2ea44f?style=for-the-badge" alt="MIT licensed"></a>
  <a href="https://github.com/rishabh3354/PDF2OCR/stargazers"><img src="https://img.shields.io/github/stars/rishabh3354/PDF2OCR?style=for-the-badge&color=f5c518" alt="GitHub stars"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Linux-Ubuntu%20%7C%20Debian%20%7C%20Fedora%20%7C%20Arch-blue?style=flat-square&logo=linux&logoColor=white" alt="Runs on Ubuntu, Debian, Fedora and Arch Linux">
  <img src="https://img.shields.io/badge/OCR-Tesseract-4285F4?style=flat-square" alt="Powered by Tesseract OCR">
  <img src="https://img.shields.io/badge/Python-PyQt5-3776AB?style=flat-square&logo=python&logoColor=white" alt="Built with Python and PyQt5">
  <img src="https://img.shields.io/badge/Pages-unlimited-success?style=flat-square" alt="No page limit">
</p>


---

## Contents

- [Screenshots](#-screenshots)
- [Install](#-install)
- [Features](#-features)
- [Supported input](#-supported-input)
- [Common tasks](#-common-tasks)
- [Run from source](#-run-from-source)
- [FAQ](#-faq)
- [How it compares](#-how-it-compares)
- [More apps](#-more-apps-by-warlord-softwares)

---

## 📸 Screenshots

| Extract text from a PDF by URL | Extract text from a local image |
|---|---|
| ![PDF2OCR extracting text from a PDF loaded by URL — original document on the left, recognised text on the right](https://raw.githubusercontent.com/rishabh3354/PDF2OCR/master/share/screenshots/pdf2ocr_url_extract.png) | ![PDF2OCR extracting text from a local image file, with output language selector and page navigation](https://raw.githubusercontent.com/rishabh3354/PDF2OCR/master/share/screenshots/pdf2ocr_file_extract.png) |

---

## 📥 Install

<p align="center">
  <a href="https://snapcraft.io/pdf2go"><img src="https://snapcraft.io/static/images/badges/en/snap-store-black.svg" height="56" alt="Install PDF2OCR from the Snap Store"></a>
</p>

```bash
sudo snap install pdf2go
```

```bash
pdf2go
```

> The snap is named **`pdf2go`** — the application shipped under that name before it was renamed, and a snap name cannot be changed without losing existing installs.

Works on Ubuntu, Debian, Fedora, Arch, Linux Mint, Pop!\_OS and any other distribution with snap support.

---

## 🌟 Features

- **Tesseract OCR** — accurate text recognition from scans, photos and screenshots.
- **Scanned PDFs** — extract text from PDF files with an unlimited number of pages.
- **Images too** — JPG, JPEG, PNG, BMP, TIFF, GIF and WebP.
- **Open from a URL** — point it at a remote PDF or image instead of downloading first.
- **Page by page** — step through a multi-page document and read the text for each page beside the original.
- **Translate the output** — convert the recognised text into another language in the app.
- **Export to `.txt`** — save the extracted text as a plain text file.
- **Caching** — previously processed pages load back quickly.
- **OCR runs locally** — scanned documents are processed on your own machine.
- **Open source** — MIT licensed, Python and PyQt5.

---

## 📄 Supported input

| | |
|---|---|
| **Documents** | PDF · scanned PDF · multi-page PDF |
| **Images** | JPG · JPEG · PNG · BMP · TIFF · GIF · WebP |
| **Sources** | Local files · folders · direct URL |
| **Output** | Editable text on screen · plain text (`.txt`) export · translated text |

---

## 🔁 Common tasks

| Task | How PDF2OCR handles it |
|---|---|
| **Extract text from a scanned PDF** | OCR every page, read the text beside the original |
| **Convert an image to text** | Drop in a JPG or PNG screenshot and pull the text out |
| **OCR a photographed document** | Works on phone photos of receipts, invoices and pages |
| **Get text from a PDF at a URL** | Paste the link — no separate download step |
| **Save the results** | Export the recognised text to a `.txt` file |
| **Translate a scanned page** | Extract the text, then translate it in the app |
| **Digitise a book chapter** | Page through a long PDF and collect the text |

---

## 🛠 Run from source

The application is MIT licensed and the full source is in [`src/`](src).

```bash
git clone https://github.com/rishabh3354/PDF2OCR.git
cd PDF2OCR
```

You'll need PyQt5 and Tesseract:

```bash
sudo apt install python3-pyqt5 tesseract-ocr
```

Then:

```bash
python3 src/pdf2go.py
```

### Building the snap

```bash
snapcraft
```

The snap consumes **[pyqt5-runtime-core22-lite](https://github.com/rishabh3354/pyqt5-runtime-core22-lite)** as a content snap rather than bundling PyQt5 — see [`snap/snapcraft.yaml`](snap/snapcraft.yaml), which also shows how `TESSDATA_PREFIX` is wired up for Tesseract inside strict confinement.

---

## ❓ FAQ

### Is PDF2OCR free?

Yes. It is free to install from the Snap Store, and the source is MIT licensed.

### Does it send my documents anywhere?

OCR runs locally with Tesseract on your own machine, so scanned documents stay on your computer. Two features do use the network: opening a file by URL, and the optional translate function.

### What file types can it read?

PDF files — including scanned and multi-page PDFs — plus JPG, JPEG, PNG, BMP, TIFF, GIF and WebP images.

### Is there a page limit?

No. It handles PDFs with an unlimited number of pages.

### Can it translate the extracted text?

Yes — the recognised text can be translated into another language inside the app.

### How accurate is the OCR?

It uses Tesseract, so accuracy depends on the source material. Clean 300 DPI scans read very well; low-resolution photos, skewed pages and unusual fonts read less well.

### Why is the snap called `pdf2go`?

The application shipped under the name PDF2Go before it was renamed. Snap names cannot be changed without losing existing installs, so `snap install pdf2go` remains correct.

### Is it available for Windows or macOS?

Not currently — the packaged build is Linux only. The source is Python and PyQt5, so it may run elsewhere, but that is untested and unsupported.

### Can I contribute?

Yes. It is MIT licensed — open an [issue](https://github.com/rishabh3354/PDF2OCR/issues) or a pull request.

---

## ⚖️ How it compares

- **Online OCR sites** — you upload the document to someone else's server, with page and size limits. That is a poor fit for contracts, IDs and medical records. PDF2OCR processes them locally.
- **`tesseract` on the command line** — the same engine, but no preview, no page navigation and no way to see the source beside the output. PDF2OCR is the graphical front end.
- **OCRmyPDF** — excellent for producing searchable PDFs in a pipeline; PDF2OCR is aimed at reading text out and exporting it, interactively.
- **Office suites** — usually no OCR at all for image-only PDFs.

---

## 🧩 More apps by Warlord Softwares

Other apps by Warlord Softwares are listed on [warlordsoftwares.com](https://warlordsoftwares.com/).

---

## 🔗 Links

- 📄 **Download page:** [rishabh3354.github.io/PDF2OCR](https://rishabh3354.github.io/PDF2OCR/)
- 📦 **Snap Store:** [snapcraft.io/pdf2go](https://snapcraft.io/pdf2go)
- 🌐 **Website:** [warlordsoftwares.com](https://warlordsoftwares.com/)
- 🐞 **Issues:** [github.com/rishabh3354/PDF2OCR/issues](https://github.com/rishabh3354/PDF2OCR/issues)

---

## 📄 License

[MIT](src/LICENSE) © Rishabh Bhardwaj / Warlord Softwares.

Built with [PyQt5](https://pypi.org/project/PyQt5/) and [Tesseract OCR](https://github.com/tesseract-ocr/tesseract).
