#!/usr/bin/env bash

set -euo pipefail

XVFB_ARGS=(-a "--server-args=-screen 0 1600x980x24")
PLAYWRIGHT_CMD=(npx playwright test "$@")

run_with_xvfb() {
  local xvfb_bin="$1"
  local xvfb_dir

  xvfb_dir="$(dirname "$xvfb_bin")"
  PATH="${xvfb_dir}:$PATH" exec "$xvfb_bin" "${XVFB_ARGS[@]}" "${PLAYWRIGHT_CMD[@]}"
}

if [[ -n "${DISPLAY:-}" && "${FORCE_XVFB:-0}" != "1" ]]; then
  exec "${PLAYWRIGHT_CMD[@]}"
fi

if [[ "$(uname -s)" == "Darwin" && "${FORCE_XVFB:-0}" != "1" ]]; then
  exec "${PLAYWRIGHT_CMD[@]}"
fi

if command -v xvfb-run >/dev/null 2>&1; then
  run_with_xvfb "$(command -v xvfb-run)"
fi

if [[ -x "/tmp/butler-xvfb/root/usr/bin/xvfb-run" ]]; then
  run_with_xvfb "/tmp/butler-xvfb/root/usr/bin/xvfb-run"
fi

cat >&2 <<'EOF'
No DISPLAY is available and xvfb-run could not be found.
Install Xvfb, or restore the local fallback at /tmp/butler-xvfb/root/usr/bin/xvfb-run.
EOF
exit 1
