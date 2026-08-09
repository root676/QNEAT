#!/usr/bin/env bash
#
# Runs the QNEAT test suite against a QGIS 4 instance.
#
#   tests/run_tests.sh                    # find a QGIS 4 and run everything
#   tests/run_tests.sh -v                 # verbose
#   tests/run_tests.sh tests.test_od_matrix
#   tests/run_tests.sh --prefix /opt/qgis4
#   tests/run_tests.sh --container        # force the containerised run
#   tests/run_tests.sh --bless            # refresh the raster golden files
#
# QGIS 4 is located in this order:
#   1. --prefix
#   2. $QGIS_PREFIX_PATH
#   3. tests/qgis_prefix.local  (one line, not tracked by git)
#   4. a few conventional source build and install locations
# A candidate only counts if python can import qgis.core from it and reports
# major version 4 or newer. If nothing qualifies, the suite falls back to a
# container image, which can be overridden with $QNEAT_TEST_IMAGE.

set -euo pipefail

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(dirname "$TESTS_DIR")"
PLUGIN_NAME="$(basename "$PLUGIN_DIR")"

PYTHON="${PYTHON:-python3}"
IMAGE="${QNEAT_TEST_IMAGE:-qgis/qgis:latest}"

FORCE_CONTAINER=0
EXPLICIT_PREFIX=""
BLESS=0
TEST_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --container) FORCE_CONTAINER=1; shift ;;
        --prefix) EXPLICIT_PREFIX="$2"; shift 2 ;;
        --prefix=*) EXPLICIT_PREFIX="${1#*=}"; shift ;;
        --bless) BLESS=1; shift ;;
        -h|--help) sed -n '2,25p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'; exit 0 ;;
        *) TEST_ARGS+=("$1"); shift ;;
    esac
done

log() { printf '[runner] %s\n' "$*"; }

# Does this prefix give us an importable QGIS 4? Echoes "pythonpath|libpath"
# on success so the caller does not have to guess the layout again.
probe_prefix() {
    local prefix="$1" pythonpath libpath
    [[ -d "$prefix" ]] || return 1

    for pythonpath in "$prefix/python" "$prefix/share/qgis/python" ""; do
        [[ -z "$pythonpath" || -d "$pythonpath" ]] || continue
        for libpath in "$prefix/lib" "$prefix/lib64" ""; do
            [[ -z "$libpath" || -d "$libpath" ]] || continue
            local version
            version="$(PYTHONPATH="$pythonpath${PYTHONPATH:+:$PYTHONPATH}" \
                       LD_LIBRARY_PATH="$libpath${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
                       QT_QPA_PLATFORM=offscreen \
                       "$PYTHON" -c 'from qgis.core import Qgis; print(Qgis.version())' \
                       2>/dev/null)" || continue
            [[ -n "$version" ]] || continue
            if [[ "${version%%.*}" -ge 4 ]]; then
                printf '%s|%s|%s' "$pythonpath" "$libpath" "$version"
                return 0
            fi
            log "  $prefix -> QGIS $version (too old, need 4+)"
            return 1
        done
    done
    return 1
}

find_prefix() {
    local candidates=()
    [[ -n "$EXPLICIT_PREFIX" ]] && candidates+=("$EXPLICIT_PREFIX")
    [[ -n "${QGIS_PREFIX_PATH:-}" ]] && candidates+=("$QGIS_PREFIX_PATH")
    if [[ -f "$TESTS_DIR/qgis_prefix.local" ]]; then
        candidates+=("$(head -n1 "$TESTS_DIR/qgis_prefix.local")")
    fi
    candidates+=(
        "$HOME/dev/cpp/QGIS/build/output"
        "$HOME/QGIS/build/output"
        "/usr/local"
        "/usr"
    )

    log 'probing for QGIS 4...'
    local candidate result
    for candidate in "${candidates[@]}"; do
        [[ -n "$candidate" ]] || continue
        if result="$(probe_prefix "$candidate")"; then
            FOUND_PREFIX="$candidate"
            FOUND_PYTHONPATH="${result%%|*}"
            local rest="${result#*|}"
            FOUND_LIBPATH="${rest%%|*}"
            FOUND_VERSION="${rest##*|}"
            log "  $candidate -> QGIS $FOUND_VERSION  OK"
            return 0
        fi
    done
    return 1
}

run_local() {
    log "using $FOUND_PREFIX (QGIS $FOUND_VERSION)"
    cd "$PLUGIN_DIR"
    QGIS_PREFIX_PATH="$FOUND_PREFIX" \
    PYTHONPATH="$FOUND_PYTHONPATH${PYTHONPATH:+:$PYTHONPATH}" \
    LD_LIBRARY_PATH="$FOUND_LIBPATH${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
    QT_QPA_PLATFORM=offscreen \
    QGIS_DISABLE_MESSAGE_HOOKS=1 \
    QGIS_DEBUG="${QGIS_DEBUG:-0}" \
    QGIS_NO_OVERRIDE_IMPORT=1 \
    QNEAT_BLESS_GOLDEN="$BLESS" \
        exec "$PYTHON" -m unittest "${TEST_ARGS[@]}"
}

run_container() {
    local engine=""
    for candidate in podman docker; do
        if command -v "$candidate" >/dev/null 2>&1; then engine="$candidate"; break; fi
    done
    if [[ -z "$engine" ]]; then
        log 'ERROR: no local QGIS 4 and neither podman nor docker is available.'
        log '       install QGIS 4, or point the runner at one:'
        log "         echo /path/to/qgis4 > $TESTS_DIR/qgis_prefix.local"
        exit 1
    fi

    log "no local QGIS 4 -> $engine run $IMAGE"
    # mounted at /src/$PLUGIN_NAME because QNEAT imports itself as a package
    local mount_flag=":ro"
    [[ "$engine" == podman ]] && mount_flag=":ro,z"
    [[ "$BLESS" == 1 ]] && mount_flag="${mount_flag/ro/rw}"

    exec "$engine" run --rm \
        -v "$PLUGIN_DIR:/src/$PLUGIN_NAME$mount_flag" \
        -w "/src/$PLUGIN_NAME" \
        -e QT_QPA_PLATFORM=offscreen \
        -e QGIS_PREFIX_PATH=/usr \
        -e QGIS_DEBUG="${QGIS_DEBUG:-0}" \
        -e PYTHONDONTWRITEBYTECODE=1 \
        -e QNEAT_BLESS_GOLDEN="$BLESS" \
        "$IMAGE" \
        python3 -m unittest "${TEST_ARGS[@]}"
}

if [[ ${#TEST_ARGS[@]} -eq 0 ]]; then
    TEST_ARGS=(discover -s tests -t . -v)
fi

if [[ "$FORCE_CONTAINER" == 1 ]]; then
    run_container
elif find_prefix; then
    run_local
else
    run_container
fi
