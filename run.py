#!/usr/bin/env python3
"""
Multi-source crawler orchestrator — Runner
Run this to start crawling. Safe to re-run (checkpoint/resume handles interruption).
Usage: python run.py [crawl|status|resume|facebook-login] [extra args]
"""
import subprocess
import sys
import os

here = os.path.dirname(os.path.abspath(__file__))
# Find the venv python — check both Windows and Unix paths
if os.name == "nt":
    venv_python = os.path.join(here, ".venv", "Scripts", "python.exe")
else:
    for candidate in (".venv/bin/python", ".venv/bin/python3", ".venv/Scripts/python.exe"):
        if os.path.isfile(os.path.join(here, candidate)):
            venv_python = os.path.join(here, candidate)
            break
    else:
        venv_python = os.path.join(here, ".venv", "bin", "python.exe")

if not os.path.isfile(venv_python):
    print("ERROR: Virtual environment not found. Run 'python setup.py' first.")
    sys.exit(1)

scraper_args = [
    venv_python,
    "main.py",
    "--config", "config/config.yaml",
    "--targets", "config/targets.yaml",
    "--verbose",
] + sys.argv[1:]

os.execv(venv_python, scraper_args)