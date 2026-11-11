#!/bin/bash
# Assembles the AppDir and packs the AppImage. Runs inside the build container
# (see build-appimage.sh): /src = repository (read-only), /out = output folder,
# /tools = appimagetool and the AppImage runtime.
set -euo pipefail

VERSION="${VERSION:?}"
ARCH=x86_64
MULTIARCH=x86_64-linux-gnu
APPDIR=/tmp/PDF2OCR.AppDir
NAME="PDF2OCR-${VERSION}-${ARCH}.AppImage"
HERE=/src/packaging/appimage

step() { printf '\n==> %s\n' "$*"; }

rm -rf "$APPDIR"
mkdir -p "$APPDIR"/usr/{bin,lib,share} "$APPDIR/usr/lib/python3/dist-packages" "$APPDIR/etc"

step "Python 3.10 and libraries"
cp /usr/bin/python3.10 "$APPDIR/usr/bin/"
cp -a /usr/lib/python3.10 "$APPDIR/usr/lib/"
( cd "$APPDIR/usr/lib/python3.10" && rm -rf test idlelib tkinter turtledemo ensurepip lib2to3 \
    pydoc_data distutils/command/*.exe sitecustomize.py site-packages dist-packages )
find "$APPDIR/usr/lib/python3.10" -name __pycache__ -prune -exec rm -rf {} +
PYQT=/usr/lib/python3/dist-packages/PyQt5
mkdir -p "$APPDIR/usr/lib/python3/dist-packages/PyQt5"
cp -a "$PYQT"/__init__.py "$PYQT"/sip.*.so "$PYQT"/QtCore.*.so "$PYQT"/QtGui.*.so \
      "$PYQT"/QtWidgets.*.so "$PYQT"/QtDBus.*.so "$APPDIR/usr/lib/python3/dist-packages/PyQt5/"
cp -a /opt/pydeps/. "$APPDIR/usr/lib/python3/dist-packages/"
rm -rf "$APPDIR/usr/lib/python3/dist-packages/bin"

step "Qt plugins"
QT_SRC=/usr/lib/$MULTIARCH/qt5/plugins
QT_DST=$APPDIR/usr/lib/$MULTIARCH/qt5/plugins
mkdir -p "$QT_DST/platforms"
cp -a "$QT_SRC"/platforms/lib{qxcb,qoffscreen,qminimal}.so "$QT_DST/platforms/"
for dir in xcbglintegrations imageformats platforminputcontexts platformthemes; do
    [ -d "$QT_SRC/$dir" ] && cp -a "$QT_SRC/$dir" "$QT_DST/"
done
# Qt looks for qt.conf next to the executable (python3.10): use our plugins only.
cat > "$APPDIR/usr/bin/qt.conf" <<EOF
[Paths]
Prefix = ..
Libraries = lib
Plugins = lib/$MULTIARCH/qt5/plugins
EOF

step "OCR, PDF and scanner tools"
for tool in tesseract pdftoppm pdftotext pdfinfo scanimage dconf; do
    cp -a "/usr/bin/$tool" "$APPDIR/usr/bin/"
done
mkdir -p "$APPDIR/usr/share/tesseract-ocr"
cp -aL /usr/share/tesseract-ocr/. "$APPDIR/usr/share/tesseract-ocr/"
mkdir -p "$APPDIR/usr/lib/$MULTIARCH"
cp -a "/usr/lib/$MULTIARCH/sane" "$APPDIR/usr/lib/$MULTIARCH/"
cp -aL /etc/sane.d "$APPDIR/etc/"
mkdir -p "$APPDIR/etc/ssl/certs"
cp -L /etc/ssl/certs/ca-certificates.crt "$APPDIR/etc/ssl/certs/"

step "PDF2OCR $VERSION"
mkdir -p "$APPDIR/usr/share/pdf2ocr"
cp -a /src/src/pdf2go.py /src/src/pdf2ocr /src/src/LICENSE "$APPDIR/usr/share/pdf2ocr/"
find "$APPDIR/usr/share/pdf2ocr" -name __pycache__ -prune -exec rm -rf {} +
install -m 755 "$HERE/AppRun" "$APPDIR/AppRun"
sed 's/^Icon=.*/Icon=pdf2go/' /src/src/pdf2go.desktop > "$APPDIR/pdf2go.desktop"
desktop-file-validate "$APPDIR/pdf2go.desktop" || true
mkdir -p "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp "$APPDIR/pdf2go.desktop" "$APPDIR/usr/share/applications/"
cp /src/src/pdf2go.png "$APPDIR/pdf2go.png"
cp /src/src/pdf2go.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/pdf2go.png"
ln -sf pdf2go.png "$APPDIR/.DirIcon"

step "Bundling shared libraries"
python3 "$HERE/bundle_libs.py" "$APPDIR"
# Absolute symlinks would point outside the AppImage: replace them with copies.
find "$APPDIR" -type l -lname '/*' | while read -r link; do
    target="$(readlink -f "$link" || true)"
    rm -f "$link"
    [ -e "$target" ] && cp -a "$target" "$link"
done

step "Precompiling Python (the AppImage is read-only)"
python3 -m compileall -q -j 0 --invalidation-mode unchecked-hash \
    "$APPDIR/usr/lib/python3.10" "$APPDIR/usr/lib/python3/dist-packages" "$APPDIR/usr/share/pdf2ocr" >/dev/null

step "Smoke test (AppDir, isolated from the build system's libraries)"
"$APPDIR/AppRun" --version
"$APPDIR/AppRun" --list-langs > /tmp/langs.txt && head -3 /tmp/langs.txt
"$APPDIR/AppRun" --to txt -l eng -o - /src/share/screenshots/01-scan-to-text.png > /tmp/ocr.txt
grep -q "Maintenance" /tmp/ocr.txt || { echo "OCR smoke test failed"; exit 1; }
echo "OCR: $(wc -w < /tmp/ocr.txt) words read from a test image"
rm -rf /tmp/smoke && mkdir /tmp/smoke
"$APPDIR/AppRun" --to pdf -l eng -o /tmp/smoke /src/share/screenshots/01-scan-to-text.png > /dev/null
"$APPDIR/AppRun" --to txt --force-ocr -l eng -o - /tmp/smoke/*.pdf | grep -q "Maintenance" \
    || { echo "Searchable PDF smoke test failed"; exit 1; }
echo "Searchable PDF: exported and read back"
QT_QPA_PLATFORM=offscreen "$APPDIR/usr/bin/python3.10" -I -c \
    "import sys; sys.path.insert(0, '$APPDIR/usr/share/pdf2ocr'); \
from PyQt5.QtWidgets import QApplication; from PyQt5 import QtDBus; import PIL, pypdf; \
app = QApplication([]); print('Qt', app.platformName(), 'Pillow', PIL.__version__, 'pypdf', pypdf.__version__)"

step "Packing $NAME"
UPDATE_INFO="gh-releases-zsync|rishabh3354|PDF2OCR|latest|PDF2OCR-*-${ARCH}.AppImage.zsync"
cd /out
rm -f "$NAME" "$NAME.zsync"
ARCH=$ARCH APPIMAGE_EXTRACT_AND_RUN=1 /tools/appimagetool --no-appstream \
    --runtime-file /tools/runtime-$ARCH -u "$UPDATE_INFO" "$APPDIR" "$NAME"
# appimagetool writes the .zsync next to the AppImage when zsyncmake is available.
[ -f "$NAME.zsync" ] || zsyncmake -u "$NAME" -o "$NAME.zsync" "$NAME"
chown "${HOST_UID:-0}:${HOST_GID:-0}" "$NAME" "$NAME.zsync"
ls -lh "/out/$NAME"
