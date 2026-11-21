"""Entry script for the frozen Windows app (OVC.exe). See README.md here."""

import sys

from ovc.app.launcher import main

if __name__ == "__main__":
    sys.exit(main())
