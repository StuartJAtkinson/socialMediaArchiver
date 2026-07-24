#!/bin/bash
# Multi-source crawler orchestrator — Linux/WSL runner.
# Usage: ./run.sh [crawl|status|resume] [main.py options]
set -e
cd "$(dirname "$0")"
if [ "$#" -eq 0 ]; then
  set -- crawl
fi
exec .venv/bin/python -u main.py "$@"
