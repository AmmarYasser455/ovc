"""The splash window must not leave Tk objects for another thread to free.

OVC shows its splash on the main thread while the server starts. Tk widgets
hold reference cycles, so after the window closed its Tk objects waited for
Python's garbage collector, which then ran on whichever thread was busy,
usually one reading a large layer. Tcl stops the whole process when its
interpreter is freed from another thread ("Tcl_AsyncDelete: async handler
deleted by the wrong thread"); on Windows that is the fatal exception
0x80000003 users saw in ovc-crash.log. Needs Tk and a display; skipped
otherwise.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = """
import gc, sys, threading
sys.path.insert(0, sys.argv[1])
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception:
    print("no-tk")
    raise SystemExit(0)
gc.collect()
from ovc.app.native import show_splash
gc.disable()  # keep cycles until a collection runs, as between automatic ones
if not show_splash(lambda: True, min_seconds=0.2):
    print("no-splash")
    raise SystemExit(0)
worker = threading.Thread(target=gc.collect)  # as a request thread would
worker.start()
worker.join()
print("ok")
"""


def test_splash_leaves_nothing_for_another_thread_to_free():
    proc = subprocess.run(
        [sys.executable, "-X", "faulthandler", "-c", SCRIPT, str(ROOT)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    out = proc.stdout.strip().splitlines()
    if out and out[-1] in ("no-tk", "no-splash"):
        pytest.skip("Tk or a display is not available")
    assert proc.returncode == 0, proc.stderr
    assert out[-1] == "ok"
