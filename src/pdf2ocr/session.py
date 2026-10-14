"""Saving the open documents and their recognized text, so work survives a
crash or restart.

Layout of the session folder (~/.local/share/pdf2ocr/session):
    session.json   pages in order, with text, edits and settings per page
    files/         copies of pasted images, screenshots and downloads (which
                   otherwise only live in the temporary folder)
    layers/        tesseract's invisible text layers, for searchable PDF export
"""

import json
import os
import shutil

from .document import Method, Page, Status

VERSION = 1


def session_dir():
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "pdf2ocr", "session")


def snapshot(pages):
    """Plain data for the pages, taken on the UI thread (cheap)."""
    result = []
    for page in pages:
        done = page.status == Status.DONE
        result.append({
            "id": page.id, "source": page.source, "kind": page.kind, "index": page.index, "count": page.count,
            "name": page.display_name, "done": done,
            "text": page.text if done else "", "edited": page.edited if done else False,
            "method": page.method.value if done and page.method else None,
            "languages": list(page.languages) if done else [],
            "confidence": page.confidence if done else None,
            "words": [[w, c, list(b)] for w, c, b in page.words] if done else [],
            "auto_rotation": page.auto_rotation, "user_rotation": page.user_rotation, "skew": page.skew,
            "force_ocr": page.force_ocr, "crop": list(page.crop) if page.crop else None,
            "text_pdf": page.text_pdf if done else None,
            "derived": page.derived, "pre_derive": list(page.pre_derive) if page.pre_derive else None,
        })
    return result


def save(data, workdir, folder=None):
    """Write a snapshot (runs in a worker thread).

    Returns {page id: {"source": ..., "text_pdf": ...}} for files that were moved
    into the session folder, so the live pages can point there and later saves
    don't copy them again."""
    folder = folder or session_dir()
    files, layers = os.path.join(folder, "files"), os.path.join(folder, "layers")
    os.makedirs(files, exist_ok=True)
    os.makedirs(layers, exist_ok=True)
    keep = set()
    copied = {}
    moved = {}
    for entry in data:
        source = entry["source"]
        if is_inside(source, workdir):
            # Pasted/downloaded files vanish with the temp folder; keep a copy.
            if source not in copied:
                target = os.path.join(files, f"{entry['id']}-{os.path.basename(source)}")
                if os.path.exists(source):
                    shutil.copy2(source, target)
                copied[source] = target
            entry["source"] = copied[source]
            moved.setdefault(entry["id"], {})["source"] = entry["source"]
        derived = entry.get("derived")
        if derived and is_inside(derived, workdir) and os.path.exists(derived):
            target = os.path.join(files, f"{entry['id']}-{os.path.basename(derived)}")
            shutil.copy2(derived, target)
            entry["derived"] = target
            moved.setdefault(entry["id"], {})["derived"] = target
        if entry.get("derived") and is_inside(entry["derived"], folder):
            keep.add(os.path.abspath(entry["derived"]))
        if is_inside(entry["source"], folder):
            keep.add(os.path.abspath(entry["source"]))
        layer = entry.get("text_pdf")
        if layer and os.path.exists(layer):
            if not is_inside(layer, folder):
                target = os.path.join(layers, f"{entry['id']}-{os.path.basename(layer)}")
                shutil.copy2(layer, target)
                entry["text_pdf"] = layer = target
                moved.setdefault(entry["id"], {})["text_pdf"] = target
            keep.add(os.path.abspath(layer))
        else:
            entry["text_pdf"] = None

    path = os.path.join(folder, "session.json")
    with open(path + ".tmp", "w", encoding="utf-8") as handle:
        json.dump({"version": VERSION, "pages": data}, handle, ensure_ascii=False)
    os.replace(path + ".tmp", path)

    for sub in (files, layers):
        for name in os.listdir(sub):
            full = os.path.abspath(os.path.join(sub, name))
            if full not in keep:
                os.remove(full)
    return moved


def load(folder=None):
    """Pages from the last session (empty list if there is none)."""
    path = os.path.join(folder or session_dir(), "session.json")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    if data.get("version") != VERSION:
        return []
    pages = []
    for entry in data.get("pages", []):
        page = Page(entry["source"], entry["kind"], entry["index"], entry["count"], entry["name"])
        page.user_rotation = entry.get("user_rotation", 0)
        page.auto_rotation = entry.get("auto_rotation", 0)
        page.skew = entry.get("skew", 0.0)
        page.force_ocr = entry.get("force_ocr", False)
        page.crop = tuple(entry["crop"]) if entry.get("crop") else None
        if entry.get("derived") and os.path.exists(entry["derived"]):
            page.derived = entry["derived"]
            page.pre_derive = tuple(entry["pre_derive"]) if entry.get("pre_derive") else None
        if entry.get("done"):
            page.status = Status.DONE
            page.text = entry.get("text", "")
            page.edited = entry.get("edited", False)
            page.method = Method(entry["method"]) if entry.get("method") else Method.OCR
            page.languages = tuple(entry.get("languages", ()))
            page.confidence = entry.get("confidence")
            page.words = [(w, c, tuple(b)) for w, c, b in entry.get("words", [])]
            layer = entry.get("text_pdf")
            page.text_pdf = layer if layer and os.path.exists(layer) else None
        pages.append(page)
    return pages


def clear(folder=None):
    shutil.rmtree(folder or session_dir(), ignore_errors=True)


def is_inside(path, folder):
    if not path or not folder:
        return False
    path, folder = os.path.abspath(path), os.path.abspath(folder)
    return os.path.commonpath([path, folder]) == folder
