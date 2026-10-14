#!/usr/bin/env python3
"""PDF2OCR launcher (the snap runs `python3 $SNAP/pdf2go.py`)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pdf2ocr.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
