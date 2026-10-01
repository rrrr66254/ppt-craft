import json
import subprocess
import sys

from helpers import SCRIPTS, STYLE


def test_run_build_executes_with_deckkit(tmp_path):
    (tmp_path / "style.json").write_text(json.dumps(STYLE), encoding="utf-8")
    script = tmp_path / "build.py"
    script.write_text(
        "from deckkit import Deck\n"
        "d = Deck('style.json')\n"
        "d.slide('안녕하세요')\n"
        "d.save('out.pptx')\n",
        encoding="utf-8",
    )
    r = subprocess.run([sys.executable, str(SCRIPTS / "run_build.py"), str(script)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "out.pptx").exists()


def test_run_build_without_argument_exits_nonzero():
    r = subprocess.run([sys.executable, str(SCRIPTS / "run_build.py")],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode != 0 and "Usage" in r.stderr
