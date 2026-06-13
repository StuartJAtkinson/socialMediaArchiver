#!/usr/bin/env python3
"""
bytebytego-grabber — Setup
Run once to create the virtual environment and install all dependencies.
Usage: python setup.py
"""
import subprocess
import sys
import os
import shutil

here = os.path.dirname(os.path.abspath(__file__))
is_windows = os.name == "nt"
pip_name = "pip.exe" if is_windows else "pip"
python_name = "python.exe" if is_windows else "python"
venv_python = os.path.join(here, ".venv", "Scripts" if is_windows else "bin", python_name)
venv_pip = os.path.join(here, ".venv", "Scripts" if is_windows else "bin", pip_name)
playwright_bin = os.path.join(
    here, ".venv", "Scripts" if is_windows else "bin",
    "playwright.exe" if is_windows else "playwright",
)


def run(cmd, check=True, **kwargs):
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if check and result.returncode != 0:
        sys.exit(result.returncode)
    return result


def main():
    print("=" * 60)
    print("bytebytego-grabber — Setup")
    print("=" * 60)

    # Create venv
    if os.path.isdir(os.path.join(here, ".venv")):
        print("\n.venv already exists — skipping venv creation.")
    else:
        print("\n[1/3] Creating virtual environment...")
        run([sys.executable, "-m", "venv", ".venv"])

    # Install deps
    print("\n[2/3] Installing dependencies...")
    run([venv_pip, "install", "--upgrade", "pip"], check=False)
    run([venv_pip, "install", "-r", "requirements.txt"])

    # Install Playwright browsers (used by the Facebook browser tiers)
    playwright_cmd = playwright_bin if os.name == "nt" else shutil.which("playwright") or playwright_bin
    if os.path.exists(playwright_cmd):
        print("\n[3/3] Installing Playwright Chromium browser...")
        run([playwright_cmd, "install", "chromium"], check=False)
    else:
        print(f"\n[3/3] Playwright not found at {playwright_bin} — run again after setup if needed.")

    print("\n" + "=" * 60)
    print("Setup complete!")
    print("=" * 60)
    print(f"\nTo run the crawler:")
    print(f"  {venv_python} main.py crawl --config config/config.yaml --targets config/targets.yaml --verbose")
    print(f"\nOr use: python run.py  (Windows: run.bat)")
    print(f"\nOther subcommands: status, resume, facebook-login")
    print(f"\nTo resume a previous crawl (picks up where it left off):")
    print(f"  {venv_python} main.py crawl --config config/config.yaml --targets config/targets.yaml --verbose")


if __name__ == "__main__":
    main()
