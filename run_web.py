#!/usr/bin/env python3
"""
Run the Social Media Archiver Web Dashboard

Usage:
    python run_web.py
    # or just:
    ./run_web.py
"""

import os
import sys
import subprocess

def main():
    """Launch the web dashboard."""
    print("🚀 Starting Social Media Archiver Web Dashboard...")
    print("📱 Open http://localhost:5000 in your browser")
    print("❌ Press Ctrl+C to stop")
    print()

    # Run the web.py Flask app
    try:
        subprocess.run([sys.executable, "web.py"], check=True)
    except KeyboardInterrupt:
        print("\n👋 Web dashboard stopped.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running web dashboard: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()