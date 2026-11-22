# Module:      __main__.py
# Description: Entry point for python3 -m connectors.plane (with the scripts folder on the module path).
# Author:      Dipen Patel (dipenpatel-dev)
# Date:
# Scope:       plane connector command line entry
# Version:     1.0
# ChangeLog:
#   - First version.

import sys

from connectors.plane.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
