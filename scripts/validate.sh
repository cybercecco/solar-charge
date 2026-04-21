#!/usr/bin/env bash
# Local validation helper for solar-charge.
#
# Runs the same checks that CI does on every push:
#   1. JSON syntax for manifest, strings and translations
#   2. Python byte-compile of the integration package
#   3. Hassfest (via the official Docker image)
#   4. HACS action (optional — needs GITHUB_TOKEN)
#
# Usage:
#     ./scripts/validate.sh               # runs 1, 2, 3
#     GITHUB_TOKEN=ghp_xxx ./scripts/validate.sh --hacs   # also runs 4
#
# Exit code is non-zero as soon as a step fails.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BLUE='\033[1;34m'
GREEN='\033[1;32m'
RED='\033[1;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

run_hacs=false
for arg in "$@"; do
    case "$arg" in
        --hacs) run_hacs=true ;;
        -h|--help)
            sed -n '2,14p' "$0"
            exit 0
            ;;
    esac
done

step() { printf "\n${BLUE}==> %s${NC}\n" "$1"; }
ok()   { printf "${GREEN}OK${NC}  %s\n" "$1"; }
fail() { printf "${RED}FAIL${NC}  %s\n" "$1"; exit 1; }
warn() { printf "${YELLOW}WARN${NC} %s\n" "$1"; }

# ---------------------------------------------------------------------------
# 1. JSON syntax
# ---------------------------------------------------------------------------
step "JSON syntax"
python3 - <<'PY' || fail "JSON validation"
import json, pathlib, sys
paths = [
    "custom_components/solar_charge/manifest.json",
    "custom_components/solar_charge/strings.json",
    "custom_components/solar_charge/services.yaml",
    "hacs.json",
]
paths += [str(p) for p in pathlib.Path("custom_components/solar_charge/translations").glob("*.json")]
bad = False
for p in paths:
    if p.endswith(".yaml"):
        continue
    try:
        json.load(open(p))
        print(f"  ok {p}")
    except Exception as exc:
        print(f"  bad {p}: {exc}", file=sys.stderr)
        bad = True
sys.exit(1 if bad else 0)
PY
ok "JSON files"

# ---------------------------------------------------------------------------
# 2. Python byte-compile
# ---------------------------------------------------------------------------
step "Python byte-compile"
python3 - <<'PY' || fail "Python compile"
import py_compile, pathlib, sys
errs = 0
for p in pathlib.Path("custom_components/solar_charge").rglob("*.py"):
    try:
        py_compile.compile(str(p), doraise=True)
        print(f"  ok {p}")
    except py_compile.PyCompileError as exc:
        print(f"  bad {p}: {exc}", file=sys.stderr)
        errs += 1
sys.exit(1 if errs else 0)
PY
ok "Python modules"

# ---------------------------------------------------------------------------
# 3. Hassfest (Docker)
# ---------------------------------------------------------------------------
step "Hassfest"
if ! command -v docker >/dev/null 2>&1; then
    warn "docker not installed — skipping hassfest"
else
    docker run --rm \
        -v "${ROOT}":/github/workspace \
        -e INPUT_PATH=/github/workspace \
        ghcr.io/home-assistant/hassfest:latest \
        >/tmp/hassfest.log 2>&1 || {
            cat /tmp/hassfest.log
            fail "hassfest reported errors"
        }
    grep -E "Invalid integrations: 0" /tmp/hassfest.log >/dev/null \
        || { cat /tmp/hassfest.log; fail "hassfest: unexpected output"; }
    ok "hassfest (see /tmp/hassfest.log for details)"
fi

# ---------------------------------------------------------------------------
# 4. HACS action (optional)
# ---------------------------------------------------------------------------
if $run_hacs; then
    step "HACS action"
    if [[ -z "${GITHUB_TOKEN:-}" ]]; then
        warn "GITHUB_TOKEN not set — skipping HACS step"
    elif ! command -v docker >/dev/null 2>&1; then
        warn "docker not installed — skipping HACS step"
    else
        docker run --rm \
            -v "${ROOT}":/github/workspace \
            -e INPUT_CATEGORY=integration \
            -e INPUT_GITHUB_TOKEN="${GITHUB_TOKEN}" \
            -e GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-cybercecco/solar-charge}" \
            ghcr.io/hacs/action:main || fail "HACS reported errors"
        ok "HACS"
    fi
fi

printf "\n${GREEN}All checks passed.${NC}\n"
