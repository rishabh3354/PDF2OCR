# Changelog

## 2026.10.1: complete redesign

PDF2OCR has been rebuilt from scratch: a new interface, a new OCR engine pipeline, and many features users asked for.

### Fixed: problems reported by users

- **OCR text was changed or "improvised"** (e.g. German *Heizungsperikelen* turned into *Hitzegefahr*, English turned into German). The old version silently ran recognized text through an online translator. Translation is gone: you now get exactly what the OCR engine read.
- **Wrong OCR language.** You can now choose the language(s) of your document (e.g. German + English). 15 languages are included and 100+ more can be downloaded in the app.
- **Is my document sent online?** No. Recognition is now 100% offline. The app no longer needs an internet connection.
- **App doesn't start / "could not load the Qt platform plugin wayland-egl".** Fixed; the app now falls back to X11/XWayland automatically. Startup problems are logged, and *Report a problem* copies diagnostics for bug reports.
- **Pages had to be scanned one at a time.** Whole documents are now recognized at once, several pages in parallel, with progress and a Stop button.
- **OCR of screen captures.** Paste screenshots with Ctrl+V, capture a screen area, or set up a keyboard shortcut that copies text from anywhere on screen.
- **Accuracy.** PDFs are scanned at 300 DPI (was 200), digital PDFs use their exact text, and pages are straightened automatically. In our tests a page tilted by 5° went from 69% character errors to 0%.

### New

**Getting text in**
- Drag & drop files and folders; open recent files
- Paste images from the clipboard; capture a screen area
- Quick capture: `pdf2go --capture` (one-click keyboard shortcut setup on GNOME)
- Scan directly from USB and network scanners, including document feeders
- Multi-page TIFF support; open files from a web address

**Recognition**
- Choose OCR languages; download more languages in the app
- Exact text from digital PDFs; OCR only where needed
- Automatic rotation of sideways/upside-down pages and straightening of tilted scans
- *Fix perspective* for photographed pages (corners found automatically)
- Optional image cleanup: enlarge screenshots, contrast, black & white, remove specks
- Page layout modes for columns, receipts/forms and single lines
- Read just a selected area, on one page or every page

**Reviewing**
- Page image and text side by side, linked word by word
- Words that may be misread are flagged in the text and on the page; confidence per page
- Find & replace across all pages (with undo)
- Page thumbnails: reorder, rotate, remove

**Saving**
- Export to TXT, Markdown, Word (.docx), LibreOffice (.odt), searchable PDF
- Tables to Excel (.xlsx) or CSV; *Copy as table* pastes straight into a spreadsheet
- Automatic saving: work survives closing the app or a crash
- Batch conversion from the command line: `pdf2go --to pdf ~/Scans` (formats: txt, md, docx, odt, pdf, xlsx, csv)

**Interface**
- New light and dark themes (follows the system), keyboard shortcuts, HiDPI icons

### Notes for Snap users
- USB scanners need a one-time permission: `sudo snap connect pdf2go:raw-usb`
- Saved work, downloaded languages and the log live in `~/snap/pdf2go/current/.local/share/pdf2ocr`
