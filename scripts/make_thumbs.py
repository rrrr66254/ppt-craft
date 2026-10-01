"""Regenerate preset thumbnails: for each preset, 3 sample slides -> render -> presets/<name>/thumb.png, and print the lint result.
Usage: python make_thumbs.py [preset name...]   (all presets if no argument)"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import lint  # noqa: E402
import render  # noqa: E402
import sample_deck  # noqa: E402
from sheet import make_sheet  # noqa: E402


def main(names=None):
    presets = ROOT / "presets"
    available = sorted(p.name for p in presets.iterdir() if (p / "style.json").exists())
    names = names or available
    unknown = [n for n in names if n not in available]
    if unknown:
        print(f"Unknown preset: {', '.join(unknown)}. Available: {', '.join(available)}", file=sys.stderr)
        return 1
    sample = json.loads((presets / "_sample.json").read_text(encoding="utf-8"))
    for name in names:
        style_path = presets / name / "style.json"
        style = sample_deck.resolve_fonts(style_path)
        wanted = json.loads(style_path.read_text(encoding="utf-8"))["font"]["head"]
        if style["font"]["head"] != wanted:
            print(f"{name}: thumbnail rendered with '{style['font']['head']}' ('{wanted}' is not installed)")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pptx = sample_deck.build(style, sample, tmp / "s.pptx")
            res = render.render(pptx, tmp / "r", width=960)
            make_sheet([res["slides"]], presets / name / "thumb.png")
            rep = lint.lint(pptx, style=style_path)
            print(name, rep["counts"], [f"{f['rule']}@{f['slide']}" for f in rep["findings"]])
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
