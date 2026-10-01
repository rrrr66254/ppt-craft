from pathlib import Path

import pytest
from PIL import Image

import render
from deckkit import Deck
from helpers import STYLE

pytestmark = pytest.mark.skipif(render.detect_backend() is None, reason="no renderer (PowerPoint/LibreOffice)")


def _deck(tmp_path, n=5):
    d = Deck(STYLE)
    for i in range(1, n + 1):
        d.slide(f"슬라이드 {i}")
    return d.save(tmp_path / "t.pptx")


def test_render_outputs_pngs_and_sheet(tmp_path):
    res = render.render(_deck(tmp_path), tmp_path / "renders", width=800, sheet=True)
    assert len(res["slides"]) == 5 and Path(res["sheet"]).exists()
    assert Image.open(res["slides"][0]).size == (800, 450)


def test_render_clears_previous_round(tmp_path):
    out = tmp_path / "renders"
    out.mkdir()
    (out / "slide-99.png").write_bytes(b"old")
    render.render(_deck(tmp_path, 1), out, width=400)
    assert not (out / "slide-99.png").exists()


import subprocess
import sys
import time


def _ps(script, **env):
    import os
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, text=True, errors="replace", timeout=120, env=dict(os.environ, **env))
    return r.returncode, r.stdout.strip(), r.stderr.strip()


win_powerpoint = pytest.mark.skipif(
    not (sys.platform == "win32" and render.detect_backend() == "powerpoint"), reason="Windows PowerPoint only")


@win_powerpoint
def test_render_path_with_quotes_and_subexpression_is_not_executed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = _deck(tmp_path, 1)
    evil = tmp_path / "x\u2019+$(New-Item PWNED.txt)+\u2019.pptx"
    src.rename(evil)
    res = render.render(evil, tmp_path / "renders", width=400)
    assert len(res["slides"]) == 1
    assert not list(tmp_path.glob("PWNED*")) and not list(Path(".").glob("PWNED*"))


@win_powerpoint
def test_render_leaves_same_file_open_in_powerpoint_untouched(tmp_path):
    for _ in range(20):  # wait briefly until the PowerPoint process quit by the previous test is gone
        if not render._powerpoint_running():
            break
        time.sleep(0.5)
    else:
        pytest.skip("PowerPoint is already running, so the cleanup step could disturb the user's work")
    src = _deck(tmp_path, 2)
    open_ps = ("$app = New-Object -ComObject PowerPoint.Application; $app.Visible = -1;"
               "$p = $app.Presentations.Open($env:PPTC_F, 0, 0, -1);"
               "$p.Slides.Item(1).Shapes.Item(1).TextFrame.TextRange.Text = 'UNSAVED EDIT'")
    probe_ps = ("$app = [Runtime.InteropServices.Marshal]::GetActiveObject('PowerPoint.Application');"
                "$p = $app.Presentations.Item(1);"
                "Write-Output ($app.Presentations.Count.ToString() + '|' + $p.Saved + '|' + "
                "$p.Slides.Item(1).Shapes.Item(1).TextFrame.TextRange.Text)")
    try:
        assert _ps(open_ps, PPTC_F=str(src))[0] == 0
        render.render(src, tmp_path / "renders", width=400)
        rc, out, err = _ps(probe_ps)
        assert rc == 0, err
        assert out == "1|0|UNSAVED EDIT", out
    finally:
        _ps("try { $app = [Runtime.InteropServices.Marshal]::GetActiveObject('PowerPoint.Application');"
            "foreach ($p in @($app.Presentations)) { $p.Saved = -1; $p.Close() }; $app.Quit() } catch {}")
