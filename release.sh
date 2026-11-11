#!/bin/bash
# Publish a PDF2OCR release on GitHub with the AppImage attached.
#
#   ./release.sh               build the AppImage and publish release v<version>
#   ./release.sh --draft       same, but as a draft you can review on GitHub first
#   ./release.sh --skip-build  upload the AppImage already in dist/
#   ./release.sh --yes         don't ask for confirmation
#
# The version comes from src/pdf2ocr/__init__.py and the release notes from the
# matching "## <version>" section of CHANGELOG.md. Running it again for the same
# version replaces the uploaded files and notes.
#
# Needs: git, Docker, and the GitHub CLI logged in (gh auth login).
set -euo pipefail
cd "$(dirname "$0")"

REPO=rishabh3354/PDF2OCR
DRAFT=() BUILD=1 ASSUME_YES=0
for arg in "$@"; do
    case "$arg" in
        --draft) DRAFT=(--draft) ;;
        --skip-build) BUILD=0 ;;
        -y|--yes) ASSUME_YES=1 ;;
        -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown option: $arg (see --help)" >&2; exit 2 ;;
    esac
done

die() { echo "Error: $*" >&2; exit 1; }
ask() {  # question -> 0 for yes
    [ "$ASSUME_YES" = 1 ] && return 0
    read -r -p "$1 [y/N] " reply
    [[ "$reply" =~ ^[Yy] ]]
}

VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/pdf2ocr/__init__.py)"
SNAP_VERSION="$(sed -n "s/^version: *'\{0,1\}\([^']*\)'\{0,1\}/\1/p" snap/snapcraft.yaml)"
TAG="v$VERSION"
APPIMAGE="dist/PDF2OCR-$VERSION-x86_64.AppImage"

echo "==> Checking PDF2OCR $VERSION"
[ -n "$VERSION" ] || die "could not read the version from src/pdf2ocr/__init__.py"
[ "$VERSION" = "$SNAP_VERSION" ] || die "version mismatch: app $VERSION, snap/snapcraft.yaml $SNAP_VERSION"
command -v gh >/dev/null || die "the GitHub CLI is missing: sudo apt install gh"
gh auth status >/dev/null 2>&1 || die "not logged in to GitHub: run 'gh auth login'"
grep -q "^## $VERSION" CHANGELOG.md || die "CHANGELOG.md has no '## $VERSION' section"
[ -z "$(git status --porcelain)" ] || die "uncommitted changes; commit them first (git status)"

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
[ "$BRANCH" = master ] || ask "You are on '$BRANCH', not master. Release from it anyway?" || exit 1
git fetch -q origin "$BRANCH" 2>/dev/null || true
COMMIT="$(git rev-parse HEAD)"
if ! git merge-base --is-ancestor "$COMMIT" "origin/$BRANCH" 2>/dev/null; then
    echo "Commit $(git rev-parse --short HEAD) is not on GitHub yet (the release tag must point at a pushed commit)."
    echo "Note: pushing to $BRANCH may also start a snap build."
    ask "Push $BRANCH to GitHub now?" || exit 1
    git push origin "$BRANCH"
fi

if [ "$BUILD" = 1 ]; then
    packaging/appimage/build-appimage.sh
fi
[ -f "$APPIMAGE" ] || die "$APPIMAGE not found (build it, or drop --skip-build)"
"$APPIMAGE" --version | grep -qx "PDF2OCR $VERSION" || die "$APPIMAGE does not report version $VERSION"

ASSETS=("$APPIMAGE")
[ -f "$APPIMAGE.zsync" ] && ASSETS+=("$APPIMAGE.zsync")
( cd dist && sha256sum "${ASSETS[@]#dist/}" > SHA256SUMS )
ASSETS+=(dist/SHA256SUMS)

NOTES="$(mktemp)"
trap 'rm -f "$NOTES"' EXIT
{
    # This version's section of the changelog, without its heading.
    awk -v v="## $VERSION" 'index($0, v) == 1 {on = 1; next} on && /^## / {exit} on' CHANGELOG.md
    cat <<EOF

## Download

**AppImage** (runs on most Linux distributions from 2022 on: Ubuntu 22.04+, Debian 12+, Fedora 36+, Mint 21+, ...):

\`\`\`
chmod +x PDF2OCR-$VERSION-x86_64.AppImage
./PDF2OCR-$VERSION-x86_64.AppImage
\`\`\`

**Snap:** \`sudo snap install pdf2go\`
EOF
} > "$NOTES"

echo
echo "Release $TAG on $REPO (commit $(git rev-parse --short "$COMMIT"))${DRAFT:+, as a draft}"
for file in "${ASSETS[@]}"; do printf '  %-48s %s\n' "$(basename "$file")" "$(du -h "$file" | cut -f1)"; done
ask "Publish it?" || exit 1

if gh release view "$TAG" -R "$REPO" >/dev/null 2>&1; then
    echo "==> $TAG exists: replacing its files and notes"
    gh release upload "$TAG" "${ASSETS[@]}" -R "$REPO" --clobber
    gh release edit "$TAG" -R "$REPO" --notes-file "$NOTES"
else
    echo "==> Creating $TAG"
    gh release create "$TAG" "${ASSETS[@]}" -R "$REPO" --target "$COMMIT" \
        --title "PDF2OCR $VERSION" --notes-file "$NOTES" "${DRAFT[@]}"
fi
git fetch -q --tags origin || true
echo
echo "Done: $(gh release view "$TAG" -R "$REPO" --json url -q .url)"
