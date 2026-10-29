#!/bin/sh
set -eu
project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_root"
if command -v uv >/dev/null 2>&1; then
    uv_binary=$(command -v uv)
else
    uv_binary="$project_root/.cache/bootstrap/uv"
    if [ ! -x "$uv_binary" ]; then
        mkdir -p "$project_root/.cache/bootstrap"
        curl -LsSf https://astral.sh/uv/0.12.9/install.sh -o .cache/bootstrap/install-uv.sh
        UV_UNMANAGED_INSTALL="$project_root/.cache/bootstrap" sh .cache/bootstrap/install-uv.sh
    fi
fi
"$uv_binary" sync --locked --extra test
"$uv_binary" run --locked agent-trace reproduce --task "${1:-d02}" --agent "${2:-current}" --trace
