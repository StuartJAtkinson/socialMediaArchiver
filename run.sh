#!/bin/bash
# Multi-source crawler orchestrator — Linux/WSL runner.
# Usage: ./run.sh [crawl|status|resume|facebook-login] [main.py options]
set -e
cd "$(dirname "$0")"
rm -rf output && mkdir output
.venv/bin/python -u main.py crawl --config config/config.yaml --targets config/targets.yaml --verbose 2>&1
