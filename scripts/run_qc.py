"""Run OVC from a source checkout: ``python scripts/run_qc.py --buildings ...``.

The command line lives in :mod:`ovc.cli`. After ``pip install`` the same
options are available as the ``ovc`` command.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ovc.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
