#!/usr/bin/env python3
"""Entry point: python stickman_video.py <command> ..."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stickman.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
