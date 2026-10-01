"""Runner for deck build scripts. Puts deckkit on the import path and runs build.py from its own folder.
Usage: python run_build.py <decks/slug/build.py>"""
import os
import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        sys.exit("Usage: python run_build.py <decks/slug/build.py>")
    script = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(script.parent))  # so helper modules next to build.py can be imported
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
    sys.argv = [str(script)] + sys.argv[2:]
    os.chdir(script.parent)
    runpy.run_path(str(script), run_name="__main__")
