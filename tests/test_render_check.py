import pytest

import render


def test_check_prints_backend(monkeypatch, capsys):
    monkeypatch.setattr(render, "detect_backend", lambda: "libreoffice")
    render.main(["--check"])
    assert capsys.readouterr().out.strip() == "libreoffice"


def test_check_exits_2_without_renderer(monkeypatch, capsys):
    monkeypatch.setattr(render, "detect_backend", lambda: None)
    with pytest.raises(SystemExit) as e:
        render.main(["--check"])
    assert e.value.code == 2
    assert "No renderer found" in capsys.readouterr().err


def _only_libreoffice(monkeypatch, converter):
    monkeypatch.setattr(render, "_has_powerpoint", lambda: False)
    monkeypatch.setattr(render, "_soffice", lambda: "soffice")
    monkeypatch.setattr(render, "_has_pdf_converter", lambda: converter)


def test_libreoffice_without_pdf_converter_is_no_backend(monkeypatch, capsys):
    _only_libreoffice(monkeypatch, False)
    assert render.detect_backend() is None
    with pytest.raises(SystemExit) as e:
        render.main(["--check"])
    assert e.value.code == 2
    assert "pymupdf" in capsys.readouterr().err


def test_libreoffice_with_pdf_converter_is_backend(monkeypatch):
    _only_libreoffice(monkeypatch, True)
    assert render.detect_backend() == "libreoffice"


@pytest.mark.parametrize("name", ["deck.pptm", "tpl.potx", "plain.pptx"])
def test_powerpoint_temp_copy_keeps_source_suffix(tmp_path, monkeypatch, name):
    src = tmp_path / name
    src.write_bytes(b"x")
    seen = {}

    def fake_run(cmd, **kw):
        seen["copy"] = kw["env"]["PPTC_SRC"]
        return type("R", (), {"returncode": 0, "stderr": "", "stdout": ""})()

    monkeypatch.setattr(render, "_powerpoint_running", lambda: True)
    monkeypatch.setattr(render.subprocess, "run", fake_run)
    render._render_powerpoint(src, tmp_path, 1600, 900)
    assert seen["copy"].endswith(src.suffix) and seen["copy"] != str(src)
