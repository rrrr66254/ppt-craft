import json
import sys

import pytest

from deckkit.fonts import find_font_file, font_dirs, has_hangul, installed_fonts


def test_font_dirs_is_list():
    assert isinstance(font_dirs(), list) and font_dirs()


def test_unknown_family_returns_none():
    assert find_font_file("NoSuchFont123") is None


def test_known_family_found_case_insensitive():
    fonts = installed_fonts()
    if not fonts:
        pytest.skip("no installed fonts")
    family = next(iter(fonts))
    assert find_font_file(family) is not None
    assert find_font_file(family.upper().replace(" ", "")) is not None


@pytest.mark.skipif(sys.platform != "win32", reason="Malgun Gothic is a Windows default font")
def test_malgun_has_hangul():
    path = find_font_file("Malgun Gothic")
    assert path and has_hangul(path)
    assert not has_hangul(find_font_file("Arial"))


@pytest.mark.skipif(sys.platform != "win32", reason=".ttc Hangul fonts are Windows-specific")
def test_ttc_family_found():
    ref = find_font_file("Gulim") or find_font_file("Batang") or find_font_file("Dotum")
    if ref is None:
        pytest.skip("no Gulim/Batang/Dotum")
    assert ref[0].lower().endswith(".ttc") and isinstance(ref[1], int)


def test_cli_list_grep_empty(capsys):
    import fonts as fonts_cli
    fonts_cli.main(["list", "--grep", "zzz_no_such_font"])
    assert json.loads(capsys.readouterr().out) == []
