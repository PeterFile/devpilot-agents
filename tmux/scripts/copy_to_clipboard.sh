#!/usr/bin/env bash
set -euo pipefail

content=$(cat | tr -d '\r')
# Update tmux buffer and system clipboard
tmux set-buffer -w -- "$content"

# WSL: use clip.exe
if command -v clip.exe >/dev/null 2>&1; then
  printf '%s' "$content" | iconv -t UTF-16LE | clip.exe || true
fi
