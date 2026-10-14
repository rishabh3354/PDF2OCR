"""Scanning with SANE through its `scanimage` command line tool.

Works with any scanner SANE supports, including most network scanners via the
driverless eSCL/AirScan backends. All calls block, so run them in a worker.
"""

import glob
import os
import re
import subprocess
from dataclasses import dataclass, field

from .tools import Cancelled, ToolError, find_tool, run

FEEDER_WORDS = ("adf", "feeder", "duplex")
MODE_LABELS = {"color": "Color", "gray": "Grayscale", "grey": "Grayscale",
               "lineart": "Black & white", "binary": "Black & white", "halftone": "Halftone"}
PREFERRED_RESOLUTIONS = (150, 200, 300, 400, 600)


@dataclass
class Scanner:
    device: str
    vendor: str
    model: str
    kind: str

    @property
    def label(self):
        name = f"{self.vendor} {self.model}".strip()
        if "airscan" in self.device or "escl" in self.device:
            name += " (network)"
        return name or self.device


@dataclass
class ScannerOptions:
    sources: list = field(default_factory=list)
    modes: list = field(default_factory=list)
    resolutions: list = field(default_factory=list)
    default_source: str = None
    default_mode: str = None


def available():
    return find_tool("scanimage") is not None


def _environment():
    env = dict(os.environ)
    snap = os.environ.get("SNAP")
    if snap:
        # SANE loads its drivers from the directories in LD_LIBRARY_PATH.
        backends = glob.glob(os.path.join(snap, "usr/lib/*/sane"))
        env["LD_LIBRARY_PATH"] = ":".join(backends + [env.get("LD_LIBRARY_PATH", "")]).strip(":")
        config = os.path.join(snap, "etc/sane.d")
        if os.path.isdir(config) and "SANE_CONFIG_DIR" not in os.environ:
            env["SANE_CONFIG_DIR"] = config
    return env


def find_scanners(token=None):
    out = run(["scanimage", "-f", "%d\t%v\t%m\t%t%n"], token=token, timeout=90, env=_environment())
    scanners = []
    for line in out.decode("utf-8", "replace").splitlines():
        parts = line.split("\t")
        if len(parts) == 4 and parts[0]:
            scanners.append(Scanner(*parts))
    return scanners


def scanner_options(device, token=None):
    out = run(["scanimage", "-d", device, "-A"], token=token, timeout=60,
              env=_environment()).decode("utf-8", "replace")
    options = ScannerOptions()
    for line in out.splitlines():
        match = re.match(r"\s+--(source|mode|resolution)\s+(.+?)\s+\[(.*?)\]", line)
        if not match:
            continue
        name, values, default = match.groups()
        if name == "resolution":
            options.resolutions = _resolutions(values)
        elif name == "source":
            options.sources = values.split("|")
            options.default_source = default
        else:
            options.modes = values.split("|")
            options.default_mode = default
    return options


def _resolutions(spec):
    spec = spec.replace("dpi", "")
    ranged = re.match(r"([\d.]+)\.\.([\d.]+)", spec)
    if ranged:
        low, high = float(ranged.group(1)), float(ranged.group(2))
        return [r for r in PREFERRED_RESOLUTIONS if low <= r <= high]
    values = []
    for part in spec.split("|"):
        try:
            values.append(int(float(part)))
        except ValueError:
            pass
    return sorted(set(values))


def is_feeder(source):
    return bool(source) and any(word in source.lower() for word in FEEDER_WORDS)


def mode_label(mode):
    return MODE_LABELS.get(mode.lower(), mode)


def scan(device, folder, prefix, source=None, mode=None, resolution=300, token=None):
    """Scan one page (flatbed) or everything in the feeder. Returns PNG paths."""
    args = ["scanimage", "-d", device, "--format=png", "--resolution", str(resolution)]
    if mode:
        args += ["--mode", mode]
    if source:
        args += ["--source", source]
    env = _environment()

    if not is_feeder(source):
        path = os.path.join(folder, f"{prefix}.png")
        data = run(args, token=token, timeout=600, env=env)
        if not data:
            raise ToolError("The scanner returned no image.")
        with open(path, "wb") as handle:
            handle.write(data)
        return [path]

    pattern = os.path.join(folder, f"{prefix}-%03d.png")
    exe = find_tool("scanimage")
    proc = subprocess.Popen([exe] + args[1:] + [f"--batch={pattern}"], stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, env=env)
    if token:
        token._register(proc)
    try:
        _out, err = proc.communicate(timeout=1800)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        raise ToolError("Scanning took too long and was stopped.")
    finally:
        if token:
            token._unregister(proc)
    pages = sorted(glob.glob(os.path.join(folder, f"{prefix}-*.png")))
    pages = [p for p in pages if os.path.getsize(p) > 0]
    if token and token.cancelled:
        if pages:
            return pages
        raise Cancelled()
    if not pages:
        message = err.decode("utf-8", "replace").strip().splitlines()
        reason = message[-1] if message else f"exit code {proc.returncode}"
        if "out of documents" in reason.lower() or "no docs" in reason.lower():
            raise ToolError("The document feeder is empty. Load the pages and try again.")
        raise ToolError(f"scanimage: {reason}")
    return pages
