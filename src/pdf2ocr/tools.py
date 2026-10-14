"""Locating and running the external command line tools (tesseract, poppler)."""

import os
import shutil
import subprocess
import threading


class Cancelled(Exception):
    """Raised inside a worker when the user cancelled the running job."""


class ToolError(Exception):
    """An external tool is missing or exited with an error."""


class CancelToken:
    """Shared between a batch of jobs so one click can stop all of them,
    including any tesseract/pdftoppm process that is currently running."""

    def __init__(self):
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._procs = set()

    @property
    def cancelled(self):
        return self._event.is_set()

    def cancel(self):
        self._event.set()
        with self._lock:
            for proc in list(self._procs):
                try:
                    proc.kill()
                except OSError:
                    pass

    def check(self):
        if self._event.is_set():
            raise Cancelled()

    def _register(self, proc):
        with self._lock:
            self._procs.add(proc)
        if self._event.is_set():
            proc.kill()

    def _unregister(self, proc):
        with self._lock:
            self._procs.discard(proc)


def find_tool(name):
    """Prefer the copy bundled inside the snap, then fall back to $PATH."""
    snap = os.environ.get("SNAP")
    if snap:
        for sub in ("usr/bin", "bin"):
            candidate = os.path.join(snap, sub, name)
            if os.access(candidate, os.X_OK):
                return candidate
    return shutil.which(name)


def run(args, token=None, timeout=None, env=None):
    """Run a command and return stdout as bytes. Raises ToolError / Cancelled."""
    exe = find_tool(args[0]) or args[0]
    try:
        proc = subprocess.Popen([exe] + list(args[1:]), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, env=env)
    except FileNotFoundError:
        raise ToolError(f"'{args[0]}' is not installed.")
    if token:
        token._register(proc)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        raise ToolError(f"{args[0]} took too long and was stopped.")
    finally:
        if token:
            token._unregister(proc)
    if token:
        token.check()
    if proc.returncode != 0:
        message = err.decode("utf-8", "replace").strip().splitlines()
        detail = message[-1] if message else f"exit code {proc.returncode}"
        raise ToolError(f"{args[0]}: {detail}")
    return out


def tesseract_version():
    exe = find_tool("tesseract")
    if not exe:
        return None
    try:
        # Older releases print the version on stderr, newer ones on stdout.
        proc = subprocess.run([exe, "--version"], capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = (proc.stdout + proc.stderr).decode("utf-8", "replace").strip().splitlines()
    return lines[0].replace("tesseract", "").strip() if lines else None


def missing_tools():
    return [name for name in ("tesseract", "pdftoppm", "pdftotext", "pdfinfo") if not find_tool(name)]
