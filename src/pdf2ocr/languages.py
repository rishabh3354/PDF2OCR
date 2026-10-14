"""Tesseract language data: names, where the models live, and downloading more.

The snap ships a fixed set of languages read-only under $SNAP. To let users add
more, we keep a writable tessdata folder in the user's data directory that holds
symlinks to the bundled files plus any downloaded models, and point tesseract at
it with --tessdata-dir.
"""

import glob
import os
import urllib.request

from .tools import Cancelled, ToolError, run

# The "fast" models: the same family Ubuntu bundles. In our tests they were as
# accurate as the larger standard/best models on real scans, and much smaller.
DOWNLOAD_URL = "https://github.com/tesseract-ocr/tessdata_fast/raw/main/{code}.traineddata"

# Script/auxiliary models that are not languages a user would pick.
HIDDEN = {"osd", "equ"}

NAMES = {
    "afr": "Afrikaans", "amh": "Amharic", "ara": "Arabic", "asm": "Assamese",
    "aze": "Azerbaijani", "aze_cyrl": "Azerbaijani (Cyrillic)", "bel": "Belarusian",
    "ben": "Bengali", "bod": "Tibetan", "bos": "Bosnian", "bre": "Breton",
    "bul": "Bulgarian", "cat": "Catalan", "ceb": "Cebuano", "ces": "Czech",
    "chi_sim": "Chinese (Simplified)", "chi_sim_vert": "Chinese (Simplified, vertical)",
    "chi_tra": "Chinese (Traditional)", "chi_tra_vert": "Chinese (Traditional, vertical)",
    "chr": "Cherokee", "cos": "Corsican", "cym": "Welsh", "dan": "Danish",
    "deu": "German", "div": "Dhivehi", "dzo": "Dzongkha", "ell": "Greek",
    "eng": "English", "enm": "English (Middle)", "epo": "Esperanto",
    "est": "Estonian", "eus": "Basque", "fao": "Faroese", "fas": "Persian",
    "fil": "Filipino", "fin": "Finnish", "fra": "French", "frk": "German (Fraktur)",
    "frm": "French (Middle)", "fry": "Frisian", "gla": "Scottish Gaelic",
    "gle": "Irish", "glg": "Galician", "grc": "Greek (Ancient)", "guj": "Gujarati",
    "hat": "Haitian Creole", "heb": "Hebrew", "hin": "Hindi", "hrv": "Croatian",
    "hun": "Hungarian", "hye": "Armenian", "iku": "Inuktitut", "ind": "Indonesian",
    "isl": "Icelandic", "ita": "Italian", "ita_old": "Italian (Old)",
    "jav": "Javanese", "jpn": "Japanese", "jpn_vert": "Japanese (vertical)",
    "kan": "Kannada", "kat": "Georgian", "kat_old": "Georgian (Old)",
    "kaz": "Kazakh", "khm": "Khmer", "kir": "Kyrgyz", "kmr": "Kurdish (Kurmanji)",
    "kor": "Korean", "kor_vert": "Korean (vertical)", "lao": "Lao", "lat": "Latin",
    "lav": "Latvian", "lit": "Lithuanian", "ltz": "Luxembourgish",
    "mal": "Malayalam", "mar": "Marathi", "mkd": "Macedonian", "mlt": "Maltese",
    "mon": "Mongolian", "mri": "Maori", "msa": "Malay", "mya": "Burmese",
    "nep": "Nepali", "nld": "Dutch", "nor": "Norwegian", "oci": "Occitan",
    "ori": "Odia", "pan": "Punjabi", "pol": "Polish", "por": "Portuguese",
    "pus": "Pashto", "que": "Quechua", "ron": "Romanian", "rus": "Russian",
    "san": "Sanskrit", "sin": "Sinhala", "slk": "Slovak", "slv": "Slovenian",
    "snd": "Sindhi", "spa": "Spanish", "spa_old": "Spanish (Old)", "sqi": "Albanian",
    "srp": "Serbian", "srp_latn": "Serbian (Latin)", "sun": "Sundanese",
    "swa": "Swahili", "swe": "Swedish", "syr": "Syriac", "tam": "Tamil",
    "tat": "Tatar", "tel": "Telugu", "tgk": "Tajik", "tha": "Thai",
    "tir": "Tigrinya", "ton": "Tongan", "tur": "Turkish", "uig": "Uyghur",
    "ukr": "Ukrainian", "urd": "Urdu", "uzb": "Uzbek", "uzb_cyrl": "Uzbek (Cyrillic)",
    "vie": "Vietnamese", "yid": "Yiddish", "yor": "Yoruba",
}

# Maps a QLocale/ISO 639-1 language code to the tesseract model name, used to
# pick a sensible default the first time the app starts.
ISO_639_1 = {
    "af": "afr", "ar": "ara", "bg": "bul", "bn": "ben", "ca": "cat", "cs": "ces",
    "da": "dan", "de": "deu", "el": "ell", "en": "eng", "es": "spa", "et": "est",
    "fa": "fas", "fi": "fin", "fr": "fra", "he": "heb", "hi": "hin", "hr": "hrv",
    "hu": "hun", "id": "ind", "it": "ita", "ja": "jpn", "ko": "kor", "lt": "lit",
    "lv": "lav", "nb": "nor", "nl": "nld", "no": "nor", "pl": "pol", "pt": "por",
    "ro": "ron", "ru": "rus", "sk": "slk", "sl": "slv", "sr": "srp", "sv": "swe",
    "ta": "tam", "te": "tel", "th": "tha", "tr": "tur", "uk": "ukr", "ur": "urd",
    "vi": "vie", "zh": "chi_sim",
}


def display_name(code):
    return NAMES.get(code, code)


def _has_models(path):
    return bool(path) and os.path.isdir(path) and bool(glob.glob(os.path.join(path, "*.traineddata")))


def bundled_tessdata_dir():
    """The read-only tessdata folder that came with tesseract (or the snap)."""
    prefix = os.environ.get("TESSDATA_PREFIX")
    candidates = []
    if prefix:
        candidates += [prefix, os.path.join(prefix, "tessdata")]
    candidates += sorted(glob.glob("/usr/share/tesseract-ocr/*/tessdata"), reverse=True)
    candidates += ["/usr/share/tessdata", "/usr/local/share/tessdata",
                   "/usr/share/tesseract/tessdata", "/opt/homebrew/share/tessdata"]
    for path in candidates:
        if _has_models(path):
            return os.path.realpath(path)
    return None


def user_tessdata_dir():
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "pdf2ocr", "tessdata")


class LanguageStore:
    """Knows which languages are installed and where tesseract should look."""

    def __init__(self):
        self.bundled_dir = bundled_tessdata_dir()
        self.user_dir = user_tessdata_dir()
        self.tessdata_dir = None
        self._prepare()

    @property
    def can_download(self):
        return self.tessdata_dir is not None

    def _prepare(self):
        if not self.bundled_dir:
            return
        try:
            os.makedirs(self.user_dir, exist_ok=True)
            # Mirror every bundled entry (models, configs/, pdf.ttf) as symlinks.
            # Recreated on every start because the snap revision in the target
            # path changes on each update.
            for entry in os.listdir(self.bundled_dir):
                link = os.path.join(self.user_dir, entry)
                target = os.path.join(self.bundled_dir, entry)
                if os.path.islink(link):
                    os.remove(link)
                elif os.path.exists(link):
                    continue  # a real downloaded file wins over the bundled one
                os.symlink(target, link)
            for link in glob.glob(os.path.join(self.user_dir, "*")):
                if os.path.islink(link) and not os.path.exists(link):
                    os.remove(link)
            self.tessdata_dir = self.user_dir
        except OSError:
            self.tessdata_dir = None

    def installed(self):
        if self.tessdata_dir:
            files = glob.glob(os.path.join(self.tessdata_dir, "*.traineddata"))
            codes = {os.path.basename(f)[:-len(".traineddata")] for f in files}
        else:
            try:
                out = run(["tesseract", "--list-langs"], timeout=15).decode("utf-8", "replace")
            except ToolError:
                return []
            codes = {line.strip() for line in out.splitlines()[1:] if line.strip()}
        return sorted((c for c in codes if c not in HIDDEN), key=display_name)

    def has_osd(self):
        directory = self.tessdata_dir or self.bundled_dir
        return bool(directory) and os.path.exists(os.path.join(directory, "osd.traineddata"))

    def is_removable(self, code):
        path = os.path.join(self.user_dir, f"{code}.traineddata")
        return os.path.isfile(path) and not os.path.islink(path)

    def remove(self, code):
        if self.is_removable(code):
            os.remove(os.path.join(self.user_dir, f"{code}.traineddata"))

    def download(self, code, progress=None, token=None):
        """Fetch a model from the official tessdata repository (blocking)."""
        if not self.can_download:
            raise ToolError("Language downloads are not available on this system.")
        target = os.path.join(self.user_dir, f"{code}.traineddata")
        partial = target + ".part"
        request = urllib.request.Request(DOWNLOAD_URL.format(code=code),
                                         headers={"User-Agent": "PDF2OCR"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response, open(partial, "wb") as out:
                total = int(response.headers.get("Content-Length") or 0)
                received = 0
                while True:
                    if token and token.cancelled:
                        raise Cancelled()
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    received += len(chunk)
                    if progress:
                        progress(received, total)
            os.replace(partial, target)
        except Cancelled:
            raise
        except OSError as error:
            raise ToolError(f"Download failed: {getattr(error, 'reason', error)}")
        finally:
            if os.path.exists(partial):
                os.remove(partial)


def default_languages(installed, locale_name):
    """English plus the user's own language, when that model is available."""
    chosen = []
    native = ISO_639_1.get(locale_name.split("_")[0].lower())
    if native in installed:
        chosen.append(native)
    if "eng" in installed and "eng" not in chosen:
        chosen.append("eng")
    if not chosen and installed:
        chosen.append(installed[0])
    return chosen
