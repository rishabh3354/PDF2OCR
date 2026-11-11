#!/usr/bin/env python3
"""Make an AppDir self-contained.

Copies every shared library the bundled programs, Python modules and plugins
need into AppDir/usr/lib, then points each ELF file at it with a relative
RUNPATH ($ORIGIN/...). Nothing relies on LD_LIBRARY_PATH, so programs the app
starts from the host (file manager, browser) are not affected.

Libraries that must match the host system (glibc, OpenGL, X11 core, fonts,
audio, USB) are left out, following the AppImage project's excludelist.
"""

import fnmatch
import os
import re
import shutil
import subprocess
import sys

EXCLUDE = [
    # glibc
    "ld-linux*.so*", "libc.so.*", "libm.so.*", "libmvec.so.*", "libdl.so.*", "libpthread.so.*",
    "librt.so.*", "libresolv.so.*", "libutil.so.*", "libanl.so.*", "libnsl.so.1", "libnss_*",
    "libBrokenLocale.so.*", "libthread_db.so.*", "libcidn.so.*",
    # compiler runtime (graphics drivers loaded from the host need the host's)
    "libstdc++.so.*", "libgcc_s.so.*",
    # graphics drivers
    "libGL.so.*", "libEGL.so.*", "libGLX.so.*", "libGLdispatch.so.*", "libOpenGL.so.*",
    "libglapi.so.*", "libdrm.so.*", "libgbm.so.*", "libxcb-dri2.so.*", "libxcb-dri3.so.*",
    # X11 core, fonts, audio, system services
    "libX11.so.*", "libX11-xcb.so.*", "libxcb.so.*", "libICE.so.*", "libSM.so.*",
    "libfontconfig.so.*", "libfreetype.so.*", "libharfbuzz.so.*", "libfribidi.so.*", "libthai.so.*",
    "libz.so.*", "libasound.so.*", "libjack.so.*", "libpipewire-*.so.*",
    "libusb-1.0.so.*", "libcom_err.so.*", "libgpg-error.so.*", "libp11-kit.so.*", "libgmp.so.*",
    "libuuid.so.*",
]

LDD_LINE = re.compile(r"^\s*(\S+)\s+=>\s+(\S+)\s+\(")
LDD_MISSING = re.compile(r"^\s*(\S+)\s+=>\s+not found")


def is_elf(path):
    if os.path.islink(path) or not os.path.isfile(path):
        return False
    with open(path, "rb") as handle:
        return handle.read(4) == b"\x7fELF"


def excluded(name):
    return any(fnmatch.fnmatch(name, pattern) for pattern in EXCLUDE)


def elf_files(root):
    for folder, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(folder, name)
            if is_elf(path):
                yield path


def dependencies(path):
    proc = subprocess.run(["ldd", path], capture_output=True, text=True)
    found, missing = [], []
    for line in proc.stdout.splitlines():
        match = LDD_LINE.match(line)
        if match:
            found.append((match.group(1), match.group(2)))
        elif LDD_MISSING.match(line):
            missing.append(LDD_MISSING.match(line).group(1))
    return found, missing


def patchelf(*args):
    return subprocess.run(["patchelf"] + list(args), capture_output=True, text=True)


def main(appdir):
    appdir = os.path.realpath(appdir)
    libdir = os.path.join(appdir, "usr", "lib")
    os.makedirs(libdir, exist_ok=True)
    checked, missing = set(), {}
    copied = 0
    while True:
        todo = [p for p in elf_files(appdir) if p not in checked]
        if not todo:
            break
        for path in todo:
            checked.add(path)
            found, absent = dependencies(path)
            for name in absent:
                missing.setdefault(name, []).append(os.path.relpath(path, appdir))
            for name, resolved in found:
                if excluded(name) or os.path.realpath(resolved).startswith(appdir + os.sep):
                    continue
                target = os.path.join(libdir, name)
                if not os.path.exists(target):
                    shutil.copy2(os.path.realpath(resolved), target)
                    copied += 1

    patched = 0
    for path in elf_files(appdir):
        current = patchelf("--print-rpath", path).stdout.strip()
        if "$ORIGIN" in current:
            continue  # pip wheels (Pillow) already point at their own libraries
        rel = os.path.relpath(libdir, os.path.dirname(path))
        rpath = "$ORIGIN" if rel == "." else f"$ORIGIN/{rel}"
        result = patchelf("--set-rpath", rpath, path)
        if result.returncode != 0:
            sys.exit(f"patchelf failed on {path}: {result.stderr.strip()}")
        patched += 1

    print(f"bundle_libs: copied {copied} libraries, set RUNPATH on {patched} files")
    # Optional plugins may reference libraries we deliberately do not ship.
    for name, users in sorted(missing.items()):
        print(f"bundle_libs: note: {name} not found (needed by {', '.join(users[:3])})")


if __name__ == "__main__":
    main(sys.argv[1])
