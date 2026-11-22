#!/usr/bin/env python3
# Module:      plane_sync.py
# Description: Run the plane connector: python3 plane_sync.py sync|drift|create ...
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       command line entry that finds the scripts folder by itself
# Version:     1.0
# ChangeLog:
#   - First version.

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from connectors.plane.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
