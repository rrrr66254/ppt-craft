"""pptx -> slide PNGs (+ contact sheet).

Usage: python render.py <pptx> --out <folder> [--width 1600] [--sheet] [--backend powerpoint|libreoffice]
       python render.py --check   (check the renderer: prints the backend name, exit code 2 if none)
Backends: Windows PowerPoint (COM) -> LibreOffice (via PDF). Exit code 2 if neither is available.
Previous slide-*.png and sheet.png in the output folder are deleted (only the latest round is kept).
Note: hidden slides are included in a PowerPoint export but dropped by the LibreOffice PDF conversion.
"""
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sheet import make_sheet, slide_pngs  # noqa: E402

INSTALL_HELP = """No renderer found. Review needs real slide captures.
- Windows: if Microsoft PowerPoint is installed it is used automatically.
- Or install LibreOffice: https://www.libreoffice.org/download/
  macOS: brew install --cask libreoffice && brew install poppler
  Linux: sudo apt install libreoffice poppler-utils
  LibreOffice also needs a PDF-to-PNG converter: poppler (pdftoppm) or pip install pymupdf"""

# Paths are passed through environment variables, not put into the script string (injection guard). The source is opened as a temporary copy:
# even if the user has the same file open, that presentation is not touched.
# PowerPoint is quit only if we launched it (PPTC_QUIT=1), no presentation is open, and no window is visible (a visible PowerPoint is never closed).
_PS = r"""
$ErrorActionPreference = 'Stop'
$app = New-Object -ComObject PowerPoint.Application
try {
  $p = $app.Presentations.Open($env:PPTC_SRC, -1, 0, 0)
  try {
    for ($i = 1; $i -le $p.Slides.Count; $i++) {
      $p.Slides.Item($i).Export((Join-Path $env:PPTC_OUT ('slide-{0:D2}.png' -f $i)), 'PNG', __W__, __H__)
    }
  } finally { $p.Close() }
} finally {
  $visible = $false
  try { $visible = ($app.Visible -eq -1) } catch {}
  if ($env:PPTC_QUIT -eq '1' -and $app.Presentations.Count -eq 0 -and -not $visible) { $app.Quit() }
}
"""


class RendererMissing(RuntimeError):
    pass


def _has_powerpoint():
    if sys.platform != "win32":
        return False
    import winreg
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "PowerPoint.Application"))
        return True
    except OSError:
        return False


def _soffice():
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    for p in (r"C:\Program Files\LibreOffice\program\soffice.exe", "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        if Path(p).exists():
            return p
    return None


def _has_pdf_converter():
    return bool(shutil.which("pdftoppm")) or importlib.util.find_spec("fitz") is not None


def detect_backend():
    if _has_powerpoint():
        return "powerpoint"
    if _soffice() and _has_pdf_converter():  # without a PDF-to-PNG converter, LibreOffice alone cannot render
        return "libreoffice"
    return None


def _powerpoint_running():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq POWERPNT.EXE", "/NH"],
                       capture_output=True, text=True, errors="replace")
    return "POWERPNT.EXE" in r.stdout.upper()


def _render_powerpoint(src, out, w, h, timeout=900):
    was_running = _powerpoint_running()
    script = _PS.replace("__W__", str(int(w))).replace("__H__", str(int(h)))
    tmp = Path(tempfile.mkdtemp())
    try:
        copy = tmp / f"deck{Path(src).suffix or '.pptx'}"  # keep .pptm/.potx/...: PowerPoint rejects a mismatched extension
        shutil.copyfile(src, copy)
        env = dict(os.environ, PPTC_SRC=str(copy), PPTC_OUT=str(out), PPTC_QUIT="0" if was_running else "1")
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                "-Command", script],
                               capture_output=True, text=True, errors="replace", timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            if not was_running:
                subprocess.run(["taskkill", "/IM", "POWERPNT.EXE", "/F"], capture_output=True)
            raise RuntimeError(f"PowerPoint render did not finish within {timeout} seconds and was stopped.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if r.returncode != 0:
        raise RuntimeError(f"PowerPoint render failed: {r.stderr.strip()}")


def _render_libreoffice(soffice, src, out, w):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # Separate profile: keeps the job from being handed to an already running LibreOffice, which would then exit immediately.
        r = subprocess.run([soffice, "-env:UserInstallation=" + (tmp / "lo-profile").as_uri(), "--headless",
                            "--convert-to", "pdf", "--outdir", str(tmp), str(src)],
                           capture_output=True, text=True, errors="replace", timeout=900)
        pdf = tmp / f"{src.stem}.pdf"
        if not pdf.exists():
            raise RuntimeError(f"LibreOffice PDF conversion failed: {r.stderr.strip()}")
        if shutil.which("pdftoppm"):
            subprocess.run(["pdftoppm", "-png", "-scale-to-x", str(w), "-scale-to-y", "-1", str(pdf), str(tmp / "p")],
                           check=True, timeout=900)
            pages = sorted(tmp.glob("p-*.png"), key=lambda p: int(p.stem.rsplit("-", 1)[1]))
        else:
            try:
                import fitz
            except ImportError:
                raise RuntimeError("No PDF-to-PNG converter. Install poppler (pdftoppm) or run pip install pymupdf.")
            pages = []
            with fitz.open(pdf) as doc:
                for i, page in enumerate(doc, 1):
                    zoom = w / page.rect.width
                    p = tmp / f"p-{i}.png"
                    page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)).save(p)
                    pages.append(p)
        for i, p in enumerate(pages, 1):
            shutil.move(str(p), out / f"slide-{i:02d}.png")


def render(src, out_dir, width=1600, sheet=False, backend=None):
    from pptx import Presentation

    src, out = Path(src).resolve(), Path(out_dir).resolve()
    prs = Presentation(str(src))  # a missing or corrupt file fails here, before the previous PNGs are deleted
    out.mkdir(parents=True, exist_ok=True)
    for old in list(out.glob("slide-*.png")) + [out / "sheet.png"]:
        old.unlink(missing_ok=True)
    height = round(width * prs.slide_height / prs.slide_width)
    backend = backend or detect_backend()
    if backend == "powerpoint":
        _render_powerpoint(src, out, width, height)
    elif backend == "libreoffice":
        soffice = _soffice()
        if not soffice:
            raise RendererMissing(INSTALL_HELP)
        _render_libreoffice(soffice, src, out, width)
    else:
        raise RendererMissing(INSTALL_HELP)
    slides = slide_pngs(out)
    if not slides:
        raise RuntimeError("The render produced no PNGs.")
    result = {"backend": backend, "slides": [str(p) for p in slides]}
    if sheet:
        rows = [slides[i:i + 4] for i in range(0, len(slides), 4)]
        result["sheet"] = str(make_sheet(rows, out / "sheet.png", numbered=True))
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="pptx -> PNG")
    ap.add_argument("pptx", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--check", action="store_true", help="only check the renderer (prints the backend name, exit code 2 if none)")
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--sheet", action="store_true")
    ap.add_argument("--backend", choices=["powerpoint", "libreoffice"])
    a = ap.parse_args(argv)
    if a.check:
        backend = detect_backend()
        if backend is None:
            print(INSTALL_HELP, file=sys.stderr)
            sys.exit(2)
        print(backend)
        return
    if not a.pptx or not a.out:
        ap.error("pptx and --out are required (use --check to only check the renderer)")
    try:
        res = render(a.pptx, a.out, a.width, a.sheet, a.backend)
    except RendererMissing:
        print(INSTALL_HELP, file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"[render] error: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    main()
