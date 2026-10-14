# PDF2OCR — Extract Text from Scanned PDFs, Photos and Screenshots on Linux (Tesseract OCR)

**PDF2OCR turns scanned PDFs, photographed pages, images and screenshots into editable text using Tesseract OCR.** Recognize whole documents at once, straighten tilted scans and phone photos, copy tables into a spreadsheet, and export to searchable PDF, Word, LibreOffice, Markdown, Excel or plain text. Everything runs offline on your own machine.

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
  <img src="https://img.shields.io/badge/Privacy-100%25%20offline-success?style=flat-square" alt="Runs 100% offline">
</p>


---

## Contents

- [Screenshots](#-screenshots)
- [Install](#-install)
- [Features](#-features)
- [Supported input and output](#-supported-input-and-output)
- [Common tasks](#-common-tasks)
- [Command line](#%EF%B8%8F-command-line)
- [Run from source](#-run-from-source)
- [FAQ](#-faq)
- [How it compares](#%EF%B8%8F-how-it-compares)
- [More apps](#-more-apps-by-warlord-softwares)

---

## 📸 Screenshots

![PDF2OCR showing a scanned three-page report: page thumbnails, the original page, and the recognised text with a word highlighted in both](https://raw.githubusercontent.com/rishabh3354/PDF2OCR/master/share/screenshots/01-scan-to-text.png)

| Copy part of a page, even tables | Straighten photographed pages |
|---|---|
| ![Selecting the table on a scanned invoice and copying it as spreadsheet cells, in dark mode](https://raw.githubusercontent.com/rishabh3354/PDF2OCR/master/share/screenshots/02-copy-area-and-tables.png) | ![A phone photo of a German letter with draggable corner handles for perspective correction](https://raw.githubusercontent.com/rishabh3354/PDF2OCR/master/share/screenshots/03-straighten-photos.png) |
| **Your language, or several at once** | **Save it the way you need it** |
| ![Choosing German and English as OCR languages for a straightened letter](https://raw.githubusercontent.com/rishabh3354/PDF2OCR/master/share/screenshots/04-languages.png) | ![The export menu: text, Word, LibreOffice, Markdown, searchable PDF, Excel and CSV](https://raw.githubusercontent.com/rishabh3354/PDF2OCR/master/share/screenshots/05-export.png) |

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

To scan with a **USB scanner** from the snap, allow access once:

```bash
sudo snap connect pdf2go:raw-usb
```

---

## 🌟 Features

**Getting text in**
- **Whole documents at once** — every page is recognised, several in parallel, with progress and a Stop button.
- **Paste or capture screenshots** — Ctrl+V a screenshot, or capture an area of the screen.
- **Quick capture from anywhere** — press a keyboard shortcut, select an area, and its text is on your clipboard (`pdf2go --capture`; one-click shortcut setup on GNOME).
- **Scan directly** — USB and network scanners via SANE, flatbed page by page or the whole document feeder.
- **Drag & drop, folders, recent files, multi-page TIFF, or a file from a URL.**

**Accurate recognition**
- **Choose the document's languages** — 15 included, 100+ more downloadable in the app. German + English for a mixed letter? Pick both.
- **Exact text from digital PDFs** — real PDF text is copied as-is; OCR is only used for scanned pages.
- **Straightens pages automatically** — sideways, upside-down and slightly tilted scans (a 5° tilt went from 69% character errors to 0% in our tests).
- **Fix perspective of phone photos** — the page corners are found automatically and the photo is flattened into a proper page.
- **Image cleanup** — enlarge small screenshots, improve contrast, black & white, remove specks.

**Reviewing and editing**
- **Page and text side by side, linked word by word** — click a word on the page to jump to it, or select text to see where it is.
- **Uncertain words are flagged** in the text and on the page, with a confidence score per page.
- **Select an area** to read just that part, on one page or every page.
- **Find & replace across all pages**, with undo.

**Saving**
- **Searchable PDF** that looks exactly like the original, plus **Word (.docx)**, **LibreOffice (.odt)**, **Markdown** and **plain text**.
- **Tables to Excel (.xlsx) or CSV** — or *Copy as table* and paste straight into a spreadsheet.
- **Automatic saving** — your pages and edits come back after a restart or crash.

**And**
- **OCR runs locally** — no internet needed, nothing is uploaded, and the text is never translated or rewritten.
- **Light and dark themes**, keyboard shortcuts, HiDPI icons.
- **Open source** — MIT licensed, Python and PyQt5.

---

## 📄 Supported input and output

| | |
|---|---|
| **Documents** | PDF · scanned PDF · multi-page PDF · multi-page TIFF |
| **Images** | JPG · JPEG · PNG · BMP · TIFF · GIF · WebP |
| **Sources** | Local files · folders · drag & drop · clipboard · screen capture · scanner · URL |
| **Output** | Searchable PDF · Word (.docx) · LibreOffice (.odt) · Markdown · plain text · Excel (.xlsx) · CSV · clipboard |

---

## 🔁 Common tasks

| Task | How PDF2OCR handles it |
|---|---|
| **Extract text from a scanned PDF** | Open it — every page is recognised, text beside the original |
| **Make a scanned PDF searchable** | Export → *Searchable PDF*: same look, selectable text |
| **Convert a screenshot to text** | Ctrl+V, the *Screenshot* button, or the quick-capture shortcut |
| **OCR a photographed document** | *Fix perspective* flattens the photo, then it is read like a scan |
| **Get a table into a spreadsheet** | Select the table → *Copy as table* → paste into Calc or Excel |
| **Read a letter in another language** | Pick its languages in the top bar (e.g. German + English) |
| **Digitise a stack of paper** | *Scan* from the document feeder, then export to Word or PDF |
| **Convert a folder of scans** | `pdf2go --to pdf ~/Scans` |

---

## ⌨️ Command line

Batch conversion needs no window, so it also works over SSH and in scripts:

```bash
pdf2go --to pdf ~/Scans                      # searchable PDFs next to the originals
pdf2go --to txt --lang deu+eng -o out/ *.pdf # text files into out/
pdf2go --to xlsx statements/                 # tables to Excel
pdf2go --to txt -o - photo.jpg               # print the text
pdf2go --capture                             # select a screen area, text to clipboard
pdf2go --list-langs
```

Formats: `txt md docx odt pdf xlsx csv`. Run `pdf2go --help` for all options.

---

## 🛠 Run from source

The application is MIT licensed and the full source is in [`src/`](src).

```bash
git clone https://github.com/rishabh3354/PDF2OCR.git
cd PDF2OCR
```

You'll need PyQt5, Tesseract, Poppler and (for scanning) SANE:

```bash
sudo apt install python3-pyqt5 tesseract-ocr poppler-utils sane-utils
pip install -r requirements.txt
```

Then:

```bash
python3 src/pdf2go.py
```

Extra OCR languages: install them with your package manager (e.g. `sudo apt install tesseract-ocr-deu`) or from inside the app.

### Building the snap

```bash
snapcraft
```

The snap consumes **[pyqt5-runtime-core22-lite](https://github.com/rishabh3354/pyqt5-runtime-core22-lite)** as a content snap rather than bundling PyQt5 — see [`snap/snapcraft.yaml`](snap/snapcraft.yaml), which also shows how `TESSDATA_PREFIX`, the SANE scanner drivers and the X11 fallback for Wayland are wired up inside strict confinement.

### Project layout

```
src/pdf2go.py            launcher (used by the snap)
src/pdf2ocr/
  app.py                 start-up, Qt platform fix, crash logging
  engine.py              OCR pipeline (render, clean up, rotate, deskew, tesseract)
  document.py            page model and file loading
  exporters.py           txt, md, docx, odt and searchable PDF
  tables.py              rebuilding tables; CSV / Excel output
  cli.py                 batch conversion from the command line
  languages.py           language names, bundled/downloaded models
  jobs.py                background workers
  session.py             autosave and restore
  scanner.py             scanning through SANE (scanimage)
  screenshot.py          screen capture (desktop portal / X11)
  quick_capture.py       --capture mode: screen area -> clipboard
  shortcut.py            GNOME keyboard shortcut for quick capture
  diagnostics.py         system report for bug reports
  settings.py            preferences
  ui/                    main window, viewer, page list, text panel, dialogs, theme
```

---

## ❓ FAQ

### Is PDF2OCR free?

Yes. It is free to install from the Snap Store, and the source is MIT licensed.

### Does it send my documents anywhere?

No. OCR runs locally with Tesseract on your own machine and works without an internet connection. The network is only used if you choose to open a file from a URL or download an additional OCR language.

### The text came out wrong or in the wrong language — what can I do?

Click the language button in the top bar and select every language that appears in the document. That is the single biggest factor for accuracy. For poor scans, try *Settings → Image cleanup*. Words the engine was unsure about are underlined so you know what to check.

### Does it translate or "improve" the text?

No. Earlier versions offered translation, which could silently change the recognised text. PDF2OCR now gives you exactly what the OCR engine read.

### What file types can it read?

PDF files — including scanned and multi-page PDFs — plus JPG, JPEG, PNG, BMP, TIFF (multi-page too), GIF and WebP images, the clipboard, screen captures and scanners.

### Is there a page limit?

No. It handles documents with any number of pages, recognising several pages in parallel.

### How accurate is the OCR?

It uses Tesseract, so accuracy depends on the source material. Clean 300 DPI scans read very well. PDF2OCR straightens tilted pages and photos, and digital PDFs keep their exact text, which helps a lot; heavy blur, tiny print and handwriting remain hard.

### The app doesn't start / "could not load the Qt platform plugin wayland-egl"

Fixed in version 2026.10.1: the app falls back to X11/XWayland automatically. If you still have trouble, run `QT_QPA_PLATFORM=xcb pdf2go` from a terminal, and use *⋮ → Report a problem*, which copies diagnostics for your bug report.

### My scanner isn't found

Switch it on and click refresh in the Scan window. With the snap, USB scanners need a one-time `sudo snap connect pdf2go:raw-usb`. Network scanners should be on the same network; some brands need their vendor driver (HP: `hplip`).

### Why is the snap called `pdf2go`?

The application shipped under the name PDF2Go before it was renamed. Snap names cannot be changed without losing existing installs, so `snap install pdf2go` remains correct.

### Is it available for Windows or macOS?

Not currently — the packaged build is Linux only. The source is Python and PyQt5, so it may run elsewhere, but that is untested and unsupported.

### Can I contribute?

Yes. It is MIT licensed — open an [issue](https://github.com/rishabh3354/PDF2OCR/issues) or a pull request.

---

## ⚖️ How it compares

- **Online OCR sites** — you upload the document to someone else's server, with page and size limits. That is a poor fit for contracts, IDs and medical records. PDF2OCR processes them locally.
- **`tesseract` on the command line** — the same engine, but no preview, no straightening, no way to see the source beside the output. PDF2OCR is the graphical front end, with a batch CLI as well.
- **OCRmyPDF** — excellent for producing searchable PDFs in a pipeline; PDF2OCR also makes searchable PDFs, but is aimed at reading, checking and reusing the text interactively.
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
- 📝 **Changelog:** [CHANGELOG.md](CHANGELOG.md)

---

## 📄 License

[MIT](src/LICENSE) © Rishabh Bhardwaj / Warlord Softwares.

Built with [PyQt5](https://pypi.org/project/PyQt5/) and [Tesseract OCR](https://github.com/tesseract-ocr/tesseract).
