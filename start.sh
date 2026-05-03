#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

rm -rf ./*.session* ./unknown*

ulimit -n 65536 || true

export PYTHONPATH="$REPO_DIR${PYTHONPATH:+:$PYTHONPATH}"

exec python3 bot.py
