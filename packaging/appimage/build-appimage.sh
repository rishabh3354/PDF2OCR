#!/bin/bash
# Builds dist/PDF2OCR-<version>-x86_64.AppImage (and its .zsync update file).
#
#   packaging/appimage/build-appimage.sh
#
# Needs Docker. Everything is built inside an Ubuntu 22.04 container, so the
# result does not depend on what is installed on this machine.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/src/pdf2ocr/__init__.py")"
OUT="$ROOT/dist"
TOOLS="$ROOT/build/appimage-tools"
IMAGE=pdf2ocr-appimage-builder

[ -n "$VERSION" ] || { echo "Could not read the version from src/pdf2ocr/__init__.py" >&2; exit 1; }
command -v docker >/dev/null || { echo "Docker is needed: sudo apt install docker.io" >&2; exit 1; }
mkdir -p "$OUT" "$TOOLS"

fetch() {  # url file
    if [ ! -s "$TOOLS/$2" ]; then
        echo "Downloading $2"
        curl -fL --retry 3 -o "$TOOLS/$2.part" "$1"
        mv "$TOOLS/$2.part" "$TOOLS/$2"
        chmod +x "$TOOLS/$2"
    fi
}
fetch https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage appimagetool
fetch https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64 runtime-x86_64

echo "==> Preparing the build container (cached after the first run)"
docker build -q -t "$IMAGE" "$ROOT/packaging/appimage" >/dev/null

echo "==> Building PDF2OCR $VERSION"
docker run --rm \
    -v "$ROOT:/src:ro" -v "$OUT:/out" -v "$TOOLS:/tools:ro" \
    -e VERSION="$VERSION" -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
    "$IMAGE" bash /src/packaging/appimage/build-in-container.sh

echo
echo "Built: $OUT/PDF2OCR-$VERSION-x86_64.AppImage"
