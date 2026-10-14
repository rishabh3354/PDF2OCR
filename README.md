# PDF2OCR

**PDF2OCR** is a fast, private Linux desktop app that turns **scanned PDFs, photos, images and screenshots** into editable text using **Tesseract OCR**.

Everything runs **100% offline on your computer**. Your documents are never uploaded, and the recognized text is never translated, "improved" or rewritten. You get exactly what the OCR engine read.

## Features

**Get text in**
* Open PDFs, PNG, JPG, TIFF (including multi-page TIFF), BMP, GIF and WebP files, or whole folders
* Drag & drop files, folders or images from other apps
* **Paste screenshots** straight from the clipboard (Ctrl+V)
* **Capture a screen area** with the Screenshot button (works on GNOME, KDE and other desktops via the desktop portal)
* **Scan directly from your scanner**: flatbed page by page, or the whole document feeder at once. Works with USB and network scanners supported by SANE, including most modern network scanners without drivers (eSCL/AirScan)
* **Quick capture from anywhere**: press a keyboard shortcut, select an area of the screen, and its text is on your clipboard. No need to open the app (`pdf2go --capture`, one-click shortcut setup on GNOME)
* Open a file from a web address

**Read just part of a page**
* Click **Select area** (or Ctrl+E, or Shift+drag on the page) and drag over any text. You get just that text, copied to the clipboard automatically
* **Read only this area** on one page or every page, to skip headers, footers, stamps or a second column. Searchable PDFs keep the text in exactly the right place

**Accurate recognition**
* **Choose the document language(s)**, e.g. German + English for a mixed letter. 15 languages are included and **100+ more** can be downloaded inside the app
* **Exact text from digital PDFs**: if a page already contains real text, it's copied as-is (instant and 100% accurate). OCR is only used for scanned pages
* Recognizes the **whole document at once**, several pages in parallel, with progress and a Stop button
* Straightens sideways and upside-down pages automatically, and **corrects slightly tilted scans** (up to 10°). A 5° tilt went from 69% character errors to 0% in our tests
* **Fix perspective** of photographed pages: the page corners are found automatically, then the photo is flattened into a proper page (with A4 / US Letter shape snapping)
* Optional image cleanup: enlarge small screenshots, improve contrast, black & white, remove specks
* Page layout modes for columns, single blocks, receipts/forms and single lines
* Scans PDFs at 300 DPI by default (up to 600 DPI for tiny print)

**Review & fix**
* Side-by-side page image and editable text, **linked word by word**: put the cursor on a word (or select text) and it lights up on the page image; click a word on the image to jump to it in the text
* Uncertain words are flagged in both places: underlined in the text and marked on the page image
* Each page shows a confidence score so you know what to double-check
* Page thumbnails with status, drag to reorder, rotate or remove pages
* View the text of all pages together
* **Find & replace across all pages** (Ctrl+F / Ctrl+H), with match case and undo

**Export**
* Plain text (.txt), Markdown (.md)
* Word document (.docx) and LibreOffice document (.odt)
* **Searchable PDF**: looks exactly like the original but the text can be searched, selected and copied
* Copy all text to the clipboard
* **Tables → Excel (.xlsx) or CSV**: rows and columns are rebuilt from the word positions (one sheet per page). Or select a table on the page and click **Copy as table**, then paste straight into LibreOffice Calc or Excel as cells

**Never lose work**
* Everything is **saved automatically** as you go. Close the app (or if it crashes) and your pages, recognized text and edits are back next time, even pasted screenshots
* **Open recent** files from the Open menu
* Prefer not to keep anything? Turn off *Settings → General → Reopen documents*; the saved copy is deleted right away

**Comfort**
* Light and dark themes (follows your system)
* **Copy diagnostics** (About dialog) and *Report a problem* gather version and system details for bug reports
* Keyboard shortcuts: Ctrl+F find, Ctrl+H replace, Ctrl+O open, Ctrl+V paste, Ctrl+E select area, Ctrl+Shift+A screenshot, Ctrl+Shift+N scan, Ctrl+R recognize, Ctrl+S save text, Ctrl+Shift+S searchable PDF, Ctrl+Shift+C copy all, Ctrl+PgUp/PgDn previous/next page, mouse wheel zooms the page (Shift+wheel scrolls)

## Install

[![Get it from the Snap Store](https://snapcraft.io/static/images/badges/en/snap-store-black.svg)](https://snapcraft.io/pdf2go)

```bash
sudo snap install pdf2go
```

Then start **PDF2OCR** from your app menu, or run `pdf2go`.

### Batch conversion from the command line

No window needed, so it also works over SSH or in scripts:

```bash
pdf2go --to pdf ~/Scans                      # searchable PDFs next to the originals
pdf2go --to txt --lang deu+eng -o out/ *.pdf # text files into out/
pdf2go --to xlsx statements/                 # tables to Excel
pdf2go --to txt -o - photo.jpg               # print the text
pdf2go --list-langs
```

Formats: `txt md docx odt pdf xlsx csv`. Other settings (image cleanup, page layout, …) follow the app's Settings window. Run `pdf2go --help` for all options.

### Run from source

```bash
sudo apt install tesseract-ocr poppler-utils python3-pyqt5 sane-utils
pip install -r requirements.txt
python3 src/pdf2go.py
```

Install extra languages with your package manager (e.g. `sudo apt install tesseract-ocr-deu`) or from inside the app via **Languages… → Download**.

## FAQ

**Is my document sent anywhere?**
No. Recognition uses the Tesseract engine on your own computer. The only network access happens when *you* choose "Open from web address" or download an additional language.

**The text comes out wrong or in the wrong language.**
Click the language button in the top bar and select every language that appears in your document (e.g. *German*). Picking the right language is the single biggest factor for accuracy. For poor scans, try **Settings → Image cleanup**.

**My scanner isn't found.**
Switch it on, then click refresh in the Scan window. With the Snap version, USB scanners need a one-time permission: `sudo snap connect pdf2go:raw-usb`. Network scanners should be on the same network. Some brands need their vendor driver (HP: `hplip`).

**The app doesn't start / "could not load the Qt platform plugin wayland-egl".**
Fixed in this version: the app now falls back to X11/XWayland automatically. If you still have trouble, start it from a terminal with `QT_QPA_PLATFORM=xcb pdf2go` and send us the log from `~/snap/pdf2go/current/.local/share/pdf2ocr/pdf2ocr.log`.

## Project layout

```
src/pdf2go.py            launcher (used by the snap)
src/pdf2ocr/
  app.py                 start-up, Qt platform fix, crash logging
  engine.py              OCR pipeline (render, clean up, rotate, tesseract)
  document.py            page model and file loading
  exporters.py           .txt, .docx and searchable PDF
  languages.py           language names, bundled/downloaded models
  jobs.py                background workers
  screenshot.py          screen capture (desktop portal / X11)
  scanner.py             scanning through SANE (scanimage)
  quick_capture.py       `--capture` mode: screen area -> clipboard
  shortcut.py            GNOME keyboard shortcut for quick capture
  diagnostics.py         system report for bug reports
  tables.py              rebuilding tables; CSV / Excel output
  cli.py                 batch conversion from the command line
  session.py             autosave and restore
  settings.py            preferences
  ui/                    main window, viewer, page list, text panel, dialogs, theme
```

**Keywords:** ocr, pdf to text, image to text, screenshot to text, scanned pdf, searchable pdf, tesseract, linux ocr, pdf2go, img2txt
