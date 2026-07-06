"""Persistent chart-render worker.

Keeps a single headless Chrome alive and renders svg->png jobs read from stdin
(one JSON object per line: {"svg": ..., "png": ...}), replying one JSON line per
job on stdout ({"ok": true} or {"ok": false, "error": ...}). Reusing the browser
amortizes its startup and, crucially, keeps its HTTP cache warm so the note
sprites (same URLs on every chart) are fetched once instead of per chart.

The parent (charts.py) respawns this on crash and recycles it periodically to
bound Chrome's memory growth.
"""

import atexit
import json
import sys
from pathlib import Path
from threading import Lock

import svg_to_png as sp
from svg_to_png import svg_to_png


def _quit_browser() -> None:
    if sp.browser is not None:
        try:
            sp.browser.quit()
        except Exception:
            pass
        sp.browser = None


def main() -> None:
    atexit.register(_quit_browser)  # close Chrome even on abrupt exit
    lock = Lock()
    try:
        for line in sys.stdin:  # ends when the parent closes our stdin
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                svg_to_png(Path(req["svg"]), Path(req["png"]), lock)
                reply = {"ok": True}
            except Exception as e:  # noqa: BLE001 - report any failure to parent
                reply = {"ok": False, "error": str(e)[:300]}
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
    finally:
        _quit_browser()


if __name__ == "__main__":
    main()
