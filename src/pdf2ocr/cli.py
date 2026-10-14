"""Command line batch conversion (no window needed, works over SSH):

    pdf2go --to pdf scans/                # searchable PDFs next to the originals
    pdf2go --to txt --lang deu+eng -o out/ letter.pdf photo.jpg
    pdf2go --to txt -o - page.png           # print the text
"""

import argparse
import os
import sys
import tempfile
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import APP_NAME, __version__

FORMATS = ("txt", "md", "docx", "odt", "pdf", "xlsx", "csv")


def is_cli(args):
    return any(arg in ("--to", "--help", "-h", "--version", "--list-langs") or arg.startswith("--to=")
               for arg in args)


def _parser():
    parser = argparse.ArgumentParser(
        prog="pdf2go", description="Extract text from PDFs, scans and images (offline, with Tesseract OCR).",
        epilog="Settings not given here (image cleanup, page layout, …) follow the app's Settings window.")
    parser.add_argument("inputs", nargs="*", help="files or folders to convert")
    parser.add_argument("--to", choices=FORMATS, help="output format")
    parser.add_argument("-l", "--lang", help="OCR languages, e.g. eng or deu+eng (default: as in the app)")
    parser.add_argument("-o", "--output", help="output folder (default: next to each input); '-' prints text")
    parser.add_argument("-j", "--jobs", type=int, default=0, help="pages recognized in parallel")
    parser.add_argument("--dpi", type=int, help="resolution for scanned PDF pages (default 300)")
    parser.add_argument("--force-ocr", action="store_true", help="OCR every page, even PDFs with real text")
    parser.add_argument("--overwrite", action="store_true", help="replace existing output files")
    parser.add_argument("--list-langs", action="store_true", help="show installed OCR languages and exit")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    return parser


def _say(message):
    print(message, file=sys.stderr, flush=True)


def main(args):
    from .document import Method, expand_paths, load_pages
    from .engine import PageJob, recognize
    from .exporters import ExportPage, export_docx, export_markdown, export_odt, export_searchable_pdf, \
        export_text, join_text
    from .languages import LanguageStore, default_languages, display_name
    from .settings import Settings
    from .tables import build_table, export_csv, export_xlsx, is_table
    from .tools import ToolError, missing_tools

    options = _parser().parse_args(args)
    store = LanguageStore()
    installed = store.installed()
    if options.list_langs:
        for code in installed:
            print(f"{code:10} {display_name(code)}")
        return 0
    if not options.to or not options.inputs:
        _parser().print_usage(sys.stderr)
        _say("error: give --to FORMAT and at least one file or folder")
        return 2
    if "tesseract" in missing_tools():
        _say("error: Tesseract OCR is not installed (sudo apt install tesseract-ocr)")
        return 1

    settings = Settings()
    if options.lang:
        languages = options.lang.split("+")
        unknown = [code for code in languages if code not in installed]
        if unknown:
            _say(f"error: language not installed: {', '.join(unknown)} (see --list-langs)")
            return 2
    else:
        languages = [c for c in settings.get("ocr/languages") if c in installed] or \
            default_languages(installed, os.environ.get("LANG", "en"))
    ocr = settings.ocr_options(store, languages)
    jobs = options.jobs or settings.get("ocr/parallel_pages")
    from dataclasses import replace
    ocr = replace(ocr, single_thread=jobs > 1, pdf_dpi=options.dpi or ocr.pdf_dpi,
                  use_text_layer=ocr.use_text_layer and not options.force_ocr)
    to_stdout = options.output == "-"
    if to_stdout and options.to not in ("txt", "md"):
        _say("error: printing ('-o -') only works with --to txt or --to md")
        return 2
    if options.output and not to_stdout:
        os.makedirs(options.output, exist_ok=True)

    files = expand_paths(options.inputs)
    if not files:
        _say("error: no supported files found")
        return 1
    workdir = tempfile.mkdtemp(prefix="pdf2ocr-cli-")
    failures = 0
    live = sys.stderr.isatty()  # progress counter only in a terminal, not in logs
    _say(f"{APP_NAME} {__version__}: {len(files)} file(s), languages {'+'.join(languages)}, output .{options.to}")
    try:
        for path in files:
            name = os.path.basename(path)
            target = None
            if not to_stdout:
                folder = options.output or os.path.dirname(os.path.abspath(path))
                suffix = " (searchable)" if options.to == "pdf" and folder == os.path.dirname(os.path.abspath(path)) else ""
                target = os.path.join(folder, os.path.splitext(name)[0] + suffix + "." + options.to)
                if os.path.exists(target) and not options.overwrite:
                    _say(f"  skip  {name}: {target} exists (use --overwrite)")
                    continue
            try:
                pages = load_pages(path)
            except ToolError as error:
                _say(f"  FAIL  {name}: {error}")
                failures += 1
                continue
            results = {}
            with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
                futures = {pool.submit(recognize, PageJob(p.id, p.kind, p.source, p.index, 0, False), ocr, workdir): p
                           for p in pages}
                for done, future in enumerate(as_completed(futures), 1):
                    page = futures[future]
                    try:
                        results[page.id] = future.result()
                    except ToolError as error:
                        _say(f"        page {page.index + 1}: {error}")
                    if len(pages) > 1 and live:
                        print(f"\r\033[K  ...   {name}: page {done}/{len(pages)}", end="", file=sys.stderr, flush=True)
            if len(pages) > 1 and live:
                print("\r\033[K", end="", file=sys.stderr)
            export = []
            for page in pages:
                result = results.get(page.id)
                export.append(ExportPage(page.label, result.text if result else "", page.kind, page.source,
                                         page.index, result.method if result else None,
                                         result.text_pdf if result else None, result.auto_rotation if result else 0,
                                         None, result.skew if result else 0.0))
            separators = settings.get("results/page_separators")
            if to_stdout:
                sys.stdout.write(join_text(export, separators))
            elif options.to == "txt":
                export_text(export, target, separators)
            elif options.to == "md":
                export_markdown(export, target)
            elif options.to == "docx":
                export_docx(export, target)
            elif options.to == "odt":
                export_odt(export, target)
            elif options.to in ("xlsx", "csv"):
                sheets = [(p.label, build_table(results[p.id].words or [])) for p in pages if p.id in results]
                sheets = [(n, rows) for n, rows in sheets if is_table(rows)]
                if not sheets:
                    _say(f"  none  {name}: no table found")
                    continue
                if options.to == "xlsx":
                    export_xlsx(sheets, target)
                else:
                    # One CSV; tables from several pages are separated by an empty row.
                    combined = []
                    for _n, rows in sheets:
                        combined += ([[]] if combined else []) + rows
                    export_csv(combined, target)
            else:
                export_searchable_pdf(export, target)
            missing = len(pages) - len(results)
            exact = sum(1 for r in results.values() if r.method == Method.TEXT_LAYER)
            note = f"{len(pages)} page{'s' if len(pages) != 1 else ''}"
            if exact:
                note += f", {exact} with exact PDF text"
            if missing:
                note += f", {missing} FAILED"
                failures += 1
            _say(f"  ok    {name} ({note})" + (f" -> {target}" if target else ""))
    except KeyboardInterrupt:
        _say("stopped")
        return 130
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return 1 if failures else 0
