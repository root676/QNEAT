#!/usr/bin/env bash
#
# package.sh - build an installable QGIS plugin ZIP from this repository.
#
# The resulting archive follows the structure expected by the QGIS plugin
# installer and by the plugins.qgis.org validator:
#
#   QNEAT-<version>.zip
#   └── QNEAT/                 <- exactly one top level folder, valid python
#       ├── __init__.py            package name ([A-Za-z][A-Za-z0-9-_]+)
#       ├── metadata.txt
#       ├── LICENSE
#       ├── QneatPlugin.py
#       ├── algs/
#       └── icons/
#
# Excluded from the archive: VCS data, __pycache__/*.pyc (rejected by the
# validator), IDE settings, the test suite and local helper scripts.
#
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR_NAME="QNEAT"
OUTPUT_DIR="$SRC/dist"
INCLUDE_TESTS=0
VERSION=""

usage() {
    cat <<'USAGE'
Usage: ./package.sh [options]

Builds a QGIS plugin ZIP in ./dist.

Options:
  -o, --output-dir DIR   Directory to write the ZIP to (default: ./dist)
  -n, --name NAME        Top level folder name inside the ZIP (default: QNEAT)
  -v, --version VERSION  Override the version read from metadata.txt
      --include-tests    Ship the tests/ directory inside the plugin
  -h, --help             Show this help
USAGE
}

while [ $# -gt 0 ]; do
    case "$1" in
        -o|--output-dir) OUTPUT_DIR="$2"; shift 2 ;;
        -n|--name)       PLUGIN_DIR_NAME="$2"; shift 2 ;;
        -v|--version)    VERSION="$2"; shift 2 ;;
        --include-tests) INCLUDE_TESTS=1; shift ;;
        -h|--help)       usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

die() { echo "ERROR: $*" >&2; exit 1; }

# --- read and validate metadata.txt -----------------------------------------

METADATA="$SRC/metadata.txt"
[ -f "$METADATA" ] || die "metadata.txt not found in $SRC"

# Reads a top level key from the [general] section of metadata.txt. Only the
# first line of a multi line value (e.g. changelog) is returned.
read_metadata() {
    sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*\(.*\)$/\1/p" "$METADATA" | head -n 1
}

# Fields the plugins.qgis.org validator insists on.
for key in name description version qgisMinimumVersion author email about tracker repository; do
    [ -n "$(read_metadata "$key")" ] || die "metadata.txt is missing the mandatory field '$key'"
done

[ -n "$VERSION" ] || VERSION="$(read_metadata version)"
[ -n "$VERSION" ] || die "could not determine the plugin version"

# The folder name inside the ZIP becomes a python package name at install time.
if ! printf '%s' "$PLUGIN_DIR_NAME" | grep -Eq '^[A-Za-z][A-Za-z0-9_-]+$'; then
    die "'$PLUGIN_DIR_NAME' is not a valid plugin folder name ([A-Za-z][A-Za-z0-9-_]+)"
fi

[ -f "$SRC/__init__.py" ] || die "__init__.py not found in $SRC"
[ -f "$SRC/LICENSE" ]     || die "LICENSE not found in $SRC (mandatory for plugins.qgis.org)"

ZIP_NAME="${PLUGIN_DIR_NAME}-${VERSION}.zip"
ZIP_PATH="$OUTPUT_DIR/$ZIP_NAME"

# --- stage the plugin tree --------------------------------------------------

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
PLUGIN_ROOT="$STAGE/$PLUGIN_DIR_NAME"
mkdir -p "$PLUGIN_ROOT"

EXCLUDES=(
    --exclude='./.git'
    --exclude='./.github'
    --exclude='./.gitignore'
    --exclude='./.gitattributes'
    --exclude='./.idea'
    --exclude='./.vscode'
    --exclude='./.settings'
    --exclude='./.project'
    --exclude='./.pydevproject'
    --exclude='./dist'
    --exclude='./deploy.sh'
    --exclude='./package.sh'
    --exclude='./todo.md'
    --exclude='__pycache__'
    --exclude='*.pyc'
    --exclude='*.pyo'
    --exclude='.DS_Store'
    --exclude='__MACOSX'
)
[ "$INCLUDE_TESTS" -eq 1 ] || EXCLUDES+=( --exclude='./tests' )

( cd "$SRC" && tar -cf - "${EXCLUDES[@]}" . ) | tar -xf - -C "$PLUGIN_ROOT"

# --- sanity check the staged tree -------------------------------------------

for required in __init__.py metadata.txt LICENSE QneatPlugin.py QneatProvider.py; do
    [ -e "$PLUGIN_ROOT/$required" ] || die "$required is missing from the staged plugin"
done

if find "$PLUGIN_ROOT" \( -name '*.pyc' -o -name '__pycache__' -o -name '.git' \) -print -quit | grep -q .; then
    die "staged plugin still contains files rejected by the QGIS plugin validator"
fi

# --- build the ZIP ----------------------------------------------------------

mkdir -p "$OUTPUT_DIR"
rm -f "$ZIP_PATH"

if command -v zip >/dev/null 2>&1; then
    # -X drops platform specific extra fields, sorted input keeps the entry
    # order stable between builds.
    ( cd "$STAGE" && find "$PLUGIN_DIR_NAME" -print | LC_ALL=C sort | zip -q -X -9 "$ZIP_PATH" -@ )
else
    python3 - "$STAGE" "$PLUGIN_DIR_NAME" "$ZIP_PATH" <<'PY'
import os, sys, zipfile
stage, root, target = sys.argv[1:4]
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
    for dirpath, dirnames, filenames in os.walk(os.path.join(stage, root)):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            zf.write(full, os.path.relpath(full, stage))
PY
fi

SIZE_BYTES="$(wc -c < "$ZIP_PATH")"
SIZE_HUMAN="$(du -h "$ZIP_PATH" | cut -f1)"

echo "Built $ZIP_PATH ($SIZE_HUMAN)"
echo "  plugin folder : $PLUGIN_DIR_NAME"
echo "  version       : $VERSION"
echo "  tests included: $([ "$INCLUDE_TESTS" -eq 1 ] && echo yes || echo no)"

# plugins.qgis.org rejects uploads larger than 20 MB.
if [ "$SIZE_BYTES" -gt $((20 * 1024 * 1024)) ]; then
    echo "WARNING: the archive exceeds the 20 MB upload limit of plugins.qgis.org" >&2
fi
