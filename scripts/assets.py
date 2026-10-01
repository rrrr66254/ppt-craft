"""Fetch license-safe assets at runtime and record their licenses.

Usage:
  python assets.py photo search "<query>" --out <W>/assets/_cand [--n 12] [--sources pexels,openverse,wikimedia,pixabay] [--cache <dir>]
  python assets.py photo get <candidate id> --cand <W>/assets/_cand --out <W>/assets [--cache <dir>]
  python assets.py credits <W>/assets [--lang ko|en]
  python assets.py icon search "<query>" [--sets lucide,tabler,...] [--limit 32] [--json] [--cache <dir>]
  python assets.py icon get <prefix:name> --color "#RRGGBB" --out <W>/assets/icons [--size 256] [--cache <dir>]
  python assets.py gen "<prompt>" --out <W>/assets/_cand [--aspect 16:9|4:3|3:2|1:1] [--n 2] [--seed N]
                      [--provider auto|cloudflare|pollinations|huggingface|horde] [--raw]
`search` writes thumbnails + candidates.json to _cand; `get` downloads one candidate through images.prep and appends to
credits.json. All HTTP goes through netutil. Exit codes: 0 ok, 1 nothing found / failed, 2 bad usage."""
import argparse
import base64
import datetime
import html
import io
import json
import os
import random
import re
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

from PIL import Image

import images
import netutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from deckkit.svg import svg_is_safe  # noqa: E402

SOURCES = json.loads((Path(__file__).resolve().parents[1] / "data" / "sources.json").read_text(encoding="utf-8"))
PHOTO = SOURCES["photo"]
LABELS = {"pexels": "Pexels", "openverse": "Openverse", "wikimedia": "Wikimedia Commons", "pixabay": "Pixabay"}
THUMB_MAX = 3_000_000
FULL_MAX = 50_000_000


def strip_html(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def _url(base, params):
    return base + "?" + urllib.parse.urlencode(params, safe=",")


# ---------- source adapters: REQUESTS[src](query, n, key) -> (url, headers); PARSERS[src](json, min_width) -> [candidate] ----------

def _openverse_request(query, n, key):
    cfg = PHOTO["openverse"]
    return _url("https://api.openverse.org/v1/images/", {  # no `category`: combined with `source` it returns 0 results
        "q": query, "license_type": cfg["license_type"], "source": ",".join(cfg["sources"]),
        "page_size": min(n, 20)}), {}


def _wikimedia_request(query, n, key):
    return _url("https://commons.wikimedia.org/w/api.php", {
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
        "gsrsearch": f'{query} {PHOTO["wikimedia"]["exclude"]}', "gsrlimit": min(n, 50),
        "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 640}), {}


def _pexels_request(query, n, key):
    return _url("https://api.pexels.com/v1/search", {"query": query, "per_page": min(n, 80)}), {"Authorization": key}


def _pixabay_request(query, n, key):
    return _url("https://pixabay.com/api/", {"key": key, "q": query, "image_type": "photo", "safesearch": "true",
                                             "per_page": min(max(n, 3), 200)}), {}


def _openverse_license(r):
    lic = (r.get("license") or "").lower()
    if not lic:
        return "unknown"
    if lic == "cc0":
        return "CC0 1.0"
    if lic == "pdm":
        return "Public Domain Mark 1.0"
    return f"CC {lic.upper()} {r.get('license_version') or ''}".strip()


def _openverse_parse(data):
    out = []
    for r in data.get("results", []):
        if r.get("filetype") not in (None, "jpg", "jpeg", "png", "webp"):  # svg/gif are no use as photos
            continue
        lic = (r.get("license") or "").lower()
        out.append({
            "id": f"openverse:{r['id']}", "source": "openverse", "title": r.get("title") or "",
            "thumb_url": r.get("thumbnail") or r.get("url"), "full_url": r.get("url"),
            "width": int(r.get("width") or 0), "height": int(r.get("height") or 0),
            "author": r.get("creator") or "unknown", "author_url": r.get("creator_url"),
            "landing_url": r.get("foreign_landing_url"), "license": _openverse_license(r),
            "license_url": r.get("license_url"), "attribution_required": lic not in ("cc0", "pdm"),
            "ai_risk": True})
    return out


def _wikimedia_parse(data):
    pages = sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    out = []
    for p in pages:
        info = (p.get("imageinfo") or [{}])[0]
        if info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        meta = info.get("extmetadata", {})
        val = lambda k: (meta.get(k) or {}).get("value")  # noqa: E731
        out.append({
            "id": f"wikimedia:{p['pageid']}", "source": "wikimedia", "title": re.sub(r"\.(jpe?g|png)$", "", re.sub(r"^File:", "", p.get("title", "")), flags=re.I),
            "thumb_url": info.get("thumburl") or info.get("url"), "full_url": info.get("url"),
            "width": int(info.get("width") or 0), "height": int(info.get("height") or 0),
            "author": strip_html(val("Artist")) or strip_html(val("Credit")) or "unknown", "author_url": None,
            "landing_url": info.get("descriptionurl"), "license": val("LicenseShortName") or "unknown",
            "license_url": val("LicenseUrl"), "attribution_required": val("AttributionRequired") == "true",
            "ai_risk": False})
    return out


def _pexels_parse(data):
    cfg = PHOTO["pexels"]
    return [{
        "id": f"pexels:{p['id']}", "source": "pexels", "title": p.get("alt") or "",
        "thumb_url": p["src"].get("medium"), "full_url": p["src"].get("original"),
        "width": int(p.get("width") or 0), "height": int(p.get("height") or 0),
        "author": p.get("photographer") or "unknown", "author_url": p.get("photographer_url"),
        "landing_url": p.get("url"), "license": cfg["license"], "license_url": cfg["license_url"],
        "attribution_required": False, "ai_risk": False} for p in data.get("photos", [])]


def _pixabay_size(h):
    """Size of what largeImageURL actually serves: the original, scaled so the longest side is at most 1280px."""
    w, ht = int(h.get("imageWidth") or 0), int(h.get("imageHeight") or 0)
    scale = min(1, 1280 / max(w, ht, 1))
    return round(w * scale), round(ht * scale)


def _pixabay_parse(data):
    cfg = PHOTO["pixabay"]
    return [{
        "id": f"pixabay:{h['id']}", "source": "pixabay", "title": (h.get("tags") or "").split(",")[0].strip(),
        "thumb_url": h.get("webformatURL"), "full_url": h.get("largeImageURL"),
        "width": _pixabay_size(h)[0], "height": _pixabay_size(h)[1],
        "author": h.get("user") or "unknown",
        "author_url": f"https://pixabay.com/users/{h.get('user')}-{h.get('user_id')}/",
        "landing_url": h.get("pageURL"), "license": cfg["license"], "license_url": cfg["license_url"],
        "attribution_required": False, "ai_risk": True} for h in data.get("hits", [])]


REQUESTS = {"openverse": _openverse_request, "wikimedia": _wikimedia_request,
            "pexels": _pexels_request, "pixabay": _pixabay_request}
_RAW_PARSERS = {"openverse": _openverse_parse, "wikimedia": _wikimedia_parse,
                "pexels": _pexels_parse, "pixabay": _pixabay_parse}


def _license_ok(name):
    up = (name or "").strip().upper()
    if not up or up == "UNKNOWN":
        return False
    return not (up.startswith("GFDL") and "CC" not in up)  # GFDL-only is impractical for slides: needs the full license text


NO_WIDTH_FILTER = {"openverse"}  # its API reports width null (Met) or <=1024 (NASA): the real size is checked after download


def _parser(src):
    def parse(data, min_width):
        floor = 0 if src in NO_WIDTH_FILTER else min_width
        return [c for c in _RAW_PARSERS[src](data)
                if c["full_url"] and c["width"] >= floor and _license_ok(c["license"])]
    return parse


PARSERS = {src: _parser(src) for src in _RAW_PARSERS}


# ---------- photo search / get ----------

def default_cache():
    plug = os.environ.get("CLAUDE_PLUGIN_DATA")
    return Path(plug) / "cache" if plug else Path.home() / ".cache" / "ppt-craft"


def _safe(s):
    return re.sub(r"[^A-Za-z0-9]", "_", s)


THUMB_EXT = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}


def _save_thumb(c, out):
    """Download the thumbnail next to candidates.json. False (with a message) if it can't be fetched or isn't a PNG/JPEG/WEBP image.
    RateLimited propagates so the caller stops hitting that source."""
    try:
        data = netutil.get_bytes(c["thumb_url"], max_bytes=THUMB_MAX)
        with Image.open(io.BytesIO(data)) as im:
            ext = THUMB_EXT.get(im.format)
            if ext is None:
                raise ValueError(f"unsupported thumbnail format {im.format}")
            im.verify()
    except netutil.RateLimited:
        raise
    except Exception as e:  # noqa: BLE001 - NetError, broken/oversized images (DecompressionBombError), ...
        print(f"[assets] skip thumbnail {c['id']}: {e}", file=sys.stderr)
        return False
    c["thumb_file"] = _safe(c["id"]) + ext
    (out / c["thumb_file"]).write_bytes(data)
    return True


def _load_list(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _hits(data):
    """How many results the API returned (all four response shapes)."""
    if not isinstance(data, dict):
        return 0
    for key in ("results", "photos", "hits"):
        if isinstance(data.get(key), list):
            return len(data[key])
    pages = (data.get("query") or {}).get("pages") if isinstance(data.get("query"), dict) else None
    return len(pages) if isinstance(pages, dict) else 0


def photo_search(a):
    if a.n < 1:
        print("[assets] --n must be at least 1", file=sys.stderr)
        return 2
    wanted = [s.strip() for s in a.sources.split(",") if s.strip()] if a.sources else list(SOURCES["photo_order"])
    unknown = [s for s in wanted if s not in REQUESTS]
    if unknown:
        print(f"[assets] unknown photo source(s): {', '.join(unknown)} (allowed: {', '.join(SOURCES['photo_order'])})",
              file=sys.stderr)
        return 2
    cache = Path(a.cache) if a.cache else default_cache()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    found = []
    for src in [s for s in SOURCES["photo_order"] if s in wanted]:
        if len(found) >= a.n:
            break
        key_env = PHOTO[src]["needs_key"]
        key = os.environ.get(key_env) if key_env else None
        if key_env and not key:
            print(f"[assets] skip {src}: {key_env} not set", file=sys.stderr)
            continue
        try:
            url, headers = REQUESTS[src](a.query, a.n, key)
            data = netutil.get_json(url, headers=headers, cache_dir=cache)
            cands = PARSERS[src](data, SOURCES["min_photo_width"])
            before = len(found)
            for c in cands:
                if len(found) >= a.n:
                    break
                if _save_thumb(c, out):
                    found.append(c)
            if len(found) == before:  # never let a source go silent
                hits = _hits(data)
                print(f"[assets] {src}: " + (f"{hits} results, 0 usable" if hits else "no results"), file=sys.stderr)
        except (netutil.RateLimited, netutil.NetError) as e:  # also a 429 on a thumbnail: stop hitting this host
            print(f"[assets] skip {src}: {e}", file=sys.stderr)
    if not found:
        print(f'[assets] no photos found for "{a.query}"', file=sys.stderr)
        return 1
    _merge_candidates(out, found)  # keeps candidates from earlier searches so `photo get` still finds their ids
    for c in found:
        print(_summary(c))
    return 0


def _download_url(rec, cache):
    """Wikimedia originals can be 50 MB+: ask the API for a 3000px rendition of the page instead (fall back to the original on a NetError)."""
    if rec["source"] != "wikimedia":
        return rec["full_url"]
    url = _url("https://commons.wikimedia.org/w/api.php", {
        "action": "query", "format": "json", "pageids": rec["id"].split(":", 1)[1], "prop": "imageinfo",
        "iiprop": "url|size|mime", "iiurlwidth": images.MAX_EDGE})
    try:
        pages = netutil.get_json(url, cache_dir=cache).get("query", {}).get("pages", {})
        info = (next(iter(pages.values()), {}).get("imageinfo") or [{}])[0]
        return info.get("thumburl") or rec["full_url"]
    except (netutil.NetError, AttributeError):  # RateLimited propagates: photo_get reports it and exits 1
        return rec["full_url"]


def _add_credit(path, credit):
    """Append a record to credits.json, replacing an earlier record for the same file."""
    images.write_json_atomic(path, [c for c in _load_list(path) if c.get("file") != credit["file"]] + [credit])


def _share_alike(license_name):
    return bool(re.search(r"(?<![A-Za-z])SA(?![A-Za-z])", license_name or ""))


def photo_get(a):
    cand = Path(a.cand)
    rec = next((c for c in _load_list(cand / "candidates.json") if c.get("id") == a.id), None)
    if rec is None:
        print(f"[assets] unknown candidate id: {a.id} (run `photo search` first; looked in {cand / 'candidates.json'})",
              file=sys.stderr)
        return 1
    out = Path(a.out)
    if rec.get("ai_generated"):  # generated candidates already live next to candidates.json
        try:
            data = (cand / rec["full_file"]).read_bytes()
        except (OSError, KeyError) as e:
            print(f"[assets] cannot read the generated image of {a.id}: {e}", file=sys.stderr)
            return 1
    else:
        try:
            data = netutil.get_bytes(_download_url(rec, Path(a.cache) if a.cache else default_cache()), max_bytes=FULL_MAX)
        except (netutil.RateLimited, netutil.NetError) as e:
            print(f"[assets] download failed: {e}", file=sys.stderr)
            return 1
    name = re.sub(r"[^A-Za-z0-9_-]", "_", a.id.replace(":", "-"))
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "download"
        tmp.write_bytes(data)
        try:
            info = images.prep(tmp, out, name, downloaded=True)
        except Exception as e:  # noqa: BLE001 - not an image PIL can read
            print(f"[assets] could not process {a.id}: {e}", file=sys.stderr)
            return 1
    info["source"] = rec.get("landing_url") or rec["id"]  # provenance instead of the temp path
    index = images.load_index(out)
    images.merge_entry(index, info)
    images.save_index(out, index)
    keys = ("source", "title", "author", "author_url", "landing_url", "license", "license_url",
            "attribution_required", "ai_risk")
    credit = {"file": info["file"], **{k: rec.get(k) for k in keys}, "fetched": datetime.date.today().isoformat()}
    if rec.get("ai_generated"):
        credit.update({k: rec.get(k) for k in ("ai_generated", "provider", "model", "prompt", "seed")})
    if _share_alike(rec.get("license")):
        credit["share_alike"] = True
    min_w = GEN.get("min_width", 960) if rec.get("ai_generated") else SOURCES["min_photo_width"]  # 1024px generated output is fine
    if info["size"][0] < min_w:  # keep the file, but let the slide builder know it is small
        credit["low_res"] = True
        print(f"[assets] warning: {info['file']} is only {info['size'][0]}px wide (source reported {rec.get('width') or '?'}px)",
              file=sys.stderr)
    path = out / "credits.json"
    _add_credit(path, credit)
    print(info["file"])
    return 0


# ---------- credits ----------

LINES = {"ko": ('사진: "{title}" — {author}, {label}, {license}', "사진: {author}, {label}, {license}"),
         "en": ('Photo: "{title}" by {author}, {label}, {license}', "Photo by {author}, {label}, {license}")}


AI_LINES = {"ko": "AI 생성 이미지 ({model}, {provider})", "en": "AI-generated image ({model} via {provider})"}


def _ai_labels(r):
    """(model label, provider label) for the disclosure line: curated labels from sources.json, else the raw values."""
    cfg = GEN.get(r.get("provider"), {})
    return (cfg.get("model_label") or r.get("model") or "unknown"), (cfg.get("label") or r.get("provider") or "unknown")


def credits_cmd(a):
    records = _load_list(Path(a.assets) / "credits.json")
    if not records:
        print("[assets] no credits recorded", file=sys.stderr)
        return 0
    records.sort(key=lambda r: not r.get("attribution_required"))  # required ones first (stable)
    for r in records:
        if r.get("source") == "iconify":  # icons need no credit line; they stay in credits.json as the license record
            continue
        required = bool(r.get("attribution_required"))
        if r.get("ai_generated"):
            model, provider = _ai_labels(r)
            line = AI_LINES[a.lang].format(model=model, provider=provider)
        else:
            title = str(r.get("title") or "").strip()
            license_text = str(r.get("license") or "unknown") + (" (SA)" if r.get("share_alike") else "")
            source = str(r.get("source") or "")
            line = LINES[a.lang][0 if title else 1].format(
                title=title, author=r.get("author") or "unknown", license=license_text, label=LABELS.get(source, source))
            if required:  # CC-style attribution wants the license link and the source page
                line += "".join(f" ({r['license_url']})" if k == "license_url" else f" {r[k]}"
                                for k in ("license_url", "landing_url") if r.get(k))
        if a.files:  # `<file>: <line>`, so the slide builder can map lines to slides by file
            print(f"{r.get('file', '?')}: {'* ' if required else ''}{line}")
        else:
            print(("* " if required else "  ") + line)
    return 0


# ---------- icons (Iconify) ----------

ICONIFY = "https://api.iconify.design"
ICON_ID = re.compile(r"^[a-z0-9][a-z0-9-]*:[a-z0-9][a-z0-9_-]*$")
COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _icon_collections(prefixes, cache):
    return netutil.get_json(_url(f"{ICONIFY}/collections", {"prefixes": ",".join(prefixes)}), cache_dir=cache)


def _icon_license(info):
    return ((info or {}).get("license") or {}).get("spdx")


def _icon_sets():
    blocked = set(SOURCES["icon_sets_blocked"])
    return [s for s in SOURCES["icon_sets_allowed"] if s not in blocked]


def icon_search(a):
    if a.limit < 1:
        print("[assets] --limit must be at least 1", file=sys.stderr)
        return 2
    allowed = _icon_sets()
    if a.sets:
        wanted = [s.strip() for s in a.sets.split(",") if s.strip()]
        bad = [s for s in wanted if s not in allowed]
        if bad:
            print(f"[assets] icon set(s) not allowed: {', '.join(bad)} (allowed: {', '.join(allowed)}; "
                  f"blocked: {', '.join(SOURCES['icon_sets_blocked'])})", file=sys.stderr)
            return 2
        allowed = [s for s in allowed if s in wanted]
    cache = Path(a.cache) if a.cache else default_cache()
    try:
        found = netutil.get_json(_url(f"{ICONIFY}/search", {"query": a.query, "prefixes": ",".join(allowed),
                                                           "limit": max(a.limit, 32)}), cache_dir=cache)
        ids = [i for i in found.get("icons", []) if ICON_ID.match(i) and i.split(":")[0] in allowed]
        prefixes = sorted({i.split(":")[0] for i in ids})
        cols = _icon_collections(prefixes, cache) if prefixes else {}
    except (netutil.RateLimited, netutil.NetError) as e:
        print(f"[assets] icon search failed: {e}", file=sys.stderr)
        return 1
    keep = [{"id": i, "license": _icon_license(cols.get(i.split(":")[0]))} for i in ids
            if _icon_license(cols.get(i.split(":")[0])) in SOURCES["icon_licenses_allowed"]][:a.limit]
    if not keep:
        print(f'[assets] no icons found for "{a.query}"', file=sys.stderr)
        return 1
    if a.json:
        print(json.dumps(keep, ensure_ascii=False, indent=1))
    else:
        for k in keep:
            print(f"{k['id']}  {k['license']}")
    return 0


def icon_get(a):
    if not ICON_ID.match(a.id):
        print(f"[assets] bad icon id: {a.id} (expected prefix:name, e.g. lucide:database)", file=sys.stderr)
        return 2
    if not COLOR.match(a.color):
        print(f"[assets] bad --color: {a.color} (expected #RRGGBB)", file=sys.stderr)
        return 2
    if not 16 <= a.size <= 4096:
        print("[assets] --size must be between 16 and 4096", file=sys.stderr)
        return 2
    prefix, name = a.id.split(":")
    if prefix in SOURCES["icon_sets_blocked"] or prefix not in SOURCES["icon_sets_allowed"]:
        why = "blocked (license or trademark)" if prefix in SOURCES["icon_sets_blocked"] else "not in the allowed list"
        print(f"[assets] icon set {prefix} refused: {why}. Allowed sets: {', '.join(_icon_sets())}", file=sys.stderr)
        return 1
    try:
        import resvg_py
    except ImportError:
        print("[assets] resvg-py missing: pip install -r requirements.txt", file=sys.stderr)
        return 1
    cache = Path(a.cache) if a.cache else default_cache()
    try:
        info = _icon_collections([prefix], cache).get(prefix)
        spdx = _icon_license(info)
        if spdx not in SOURCES["icon_licenses_allowed"]:
            print(f"[assets] icon set {prefix} refused: license {spdx or 'unknown'} is not one of "
                  f"{', '.join(SOURCES['icon_licenses_allowed'])}", file=sys.stderr)
            return 1
        svg = netutil.get_bytes(_url(f"{ICONIFY}/{prefix}/{name}.svg", {"color": a.color, "height": a.size}),
                                max_bytes=1_000_000).decode("utf-8")
    except (netutil.RateLimited, netutil.NetError, UnicodeDecodeError) as e:
        print(f"[assets] icon download failed: {e}", file=sys.stderr)
        return 1
    if "<svg" not in svg[:500]:
        print(f"[assets] icon download failed: {a.id} did not return an SVG", file=sys.stderr)
        return 1
    if not svg_is_safe(svg):
        print(f"[assets] icon refused: {a.id} contains external references or scripts", file=sys.stderr)
        return 1
    try:
        png = bytes(resvg_py.svg_to_bytes(svg_string=svg, height=a.size))
    except Exception as e:  # noqa: BLE001 - resvg raises a plain error on unusable SVG
        print(f"[assets] could not render {a.id}: {e}", file=sys.stderr)
        return 1
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{prefix}-{name}"
    (out / f"{stem}.svg").write_text(svg, encoding="utf-8")
    (out / f"{stem}.png").write_bytes(png)
    credit = {"file": f"{out.name}/{stem}.svg", "source": "iconify", "title": a.id,
              "author": ((info or {}).get("author") or {}).get("name") or "unknown",
              "author_url": ((info or {}).get("author") or {}).get("url"),
              "landing_url": f"https://icon-sets.iconify.design/{prefix}/{name}/", "license": spdx,
              "license_url": (info.get("license") or {}).get("url"), "attribution_required": False,
              "ai_risk": False, "fetched": datetime.date.today().isoformat()}
    path = out.parent / "credits.json"
    _add_credit(path, credit)
    print(f"{stem}.svg {stem}.png")
    return 0


# ---------- AI image generation ----------
# Verified 2026-10-01 against the official docs (URLs only):
#   Cloudflare  https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/  (POST .../ai/run/@cf/black-forest-labs/flux-1-schnell,
#               body prompt/seed/steps only: no width/height, so we center-crop; REST response is {"result": {"image": b64 jpeg}, "success": true})
#   Pollinations https://github.com/pollinations/pollinations/blob/main/APIDOCS.md  (GET https://gen.pollinations.ai/image/{prompt}?model=&width=&height=&seed=,
#               Authorization: Bearer <key>; model id from https://gen.pollinations.ai/image/models is black-forest-labs/flux.1-schnell, alias "flux")
#   Hugging Face https://huggingface.co/docs/inference-providers/tasks/text-to-image and the huggingface_hub source
#               (inference/_providers/nscale.py). FLUX.1-schnell is not served by hf-inference (its {"inputs","parameters"} shape): per
#               https://huggingface.co/api/models/black-forest-labs/FLUX.1-schnell?expand[]=inferenceProviderMapping it is served by nscale/fal-ai/
#               wavespeed. We use the router's nscale route: POST https://router.huggingface.co/nscale/v1/images/generations
#               {"response_format": "b64_json", "prompt", "model", "size": "WxH"} -> {"data": [{"b64_json": ...}]} (no seed parameter)
#   AI Horde    https://aihorde.net/api/swagger.json  (POST /v2/generate/async with apikey + Client-Agent headers -> {"id"};
#               GET /v2/generate/check/{id} -> {"done", "faulted"}; GET /v2/generate/status/{id} -> generations[].img/model/censored;
#               DELETE /v2/generate/status/{id}; params width/height 64..3072 multiples of 64, seed is a string; the 576px anonymous cap is server-side)

GEN = SOURCES["generate"]
ASPECTS = {"16:9": (1344, 768), "4:3": (1152, 864), "3:2": (1216, 800), "1:1": (1024, 1024)}
HORDE = "https://aihorde.net/api/v2"
HORDE_TIMEOUT, HORDE_POLL = 180, 3


PROMPT_MAX = 2048  # Cloudflare's limit; applied to every provider so the stored prompt is what was sent


def _strip_banned(prompt):
    """Drop banned (AI-look) words and tidy whitespace/commas. Returns (text, removed words)."""
    removed = []
    for word in GEN["banned_words"]:
        pat = re.compile(r"(?<![A-Za-z0-9-])" + re.escape(word) + r"(?![A-Za-z0-9-])", re.I)  # non-ASCII neighbours (Korean particles) still match
        if pat.search(prompt):
            removed.append(word)
            prompt = pat.sub("", prompt)
    prompt = re.sub(r"\s+", " ", prompt)
    prompt = re.sub(r"\s+,", ",", prompt)
    return re.sub(r"(,\s*)+,", ",", prompt).strip(" ,"), removed


def clean_prompt(prompt):
    """Drop banned (AI-look) words, then append the style suffix (the user part is cut so the result fits PROMPT_MAX).
    Returns (final prompt, removed words)."""
    prompt, removed = _strip_banned(prompt)
    prompt = prompt[:max(0, PROMPT_MAX - len(GEN["style_suffix"]) - 2)].rstrip(" ,")
    return (f"{prompt}, {GEN['style_suffix']}" if prompt else ""), removed


def horde_size(w, h, cap=None):
    """Scale so the longest side is at most `cap` (default: the horde max_side), each side a multiple of 64."""
    cap = cap or GEN["horde"]["max_side"]
    s = min(1.0, cap / max(w, h))
    limit = cap // 64 * 64
    return tuple(min(limit, max(64, round(v * s / 64) * 64)) for v in (w, h))


def _env(provider):
    need = GEN[provider]["needs"]
    return {k: os.environ[k] for k in need} if all(os.environ.get(k) for k in need) else None


def _gen_cloudflare(prompt, w, h, seed, env):
    cfg = GEN["cloudflare"]
    url = f"https://api.cloudflare.com/client/v4/accounts/{env['CLOUDFLARE_ACCOUNT_ID']}/ai/run/{cfg['model']}"
    try:
        d = netutil.post_json(url, {"prompt": prompt, "steps": 4, "seed": seed},
                              headers={"Authorization": f"Bearer {env['CLOUDFLARE_API_TOKEN']}"})
    except netutil.NetError as e:  # the URL carries the account id: report the host and the reason only
        raise netutil.NetError("api.cloudflare.com -> " + str(e).rpartition(" -> ")[2]) from None
    try:
        return base64.b64decode((d.get("result") or d)["image"]), cfg["model"]
    except (KeyError, TypeError, ValueError, AttributeError):
        raise netutil.NetError("cloudflare: unexpected response (no result.image)") from None


def _gen_pollinations(prompt, w, h, seed, env):
    cfg = GEN["pollinations"]
    url = (f"https://gen.pollinations.ai/image/{urllib.parse.quote(prompt, safe='')}?"
           + urllib.parse.urlencode({"model": cfg["model"], "width": w, "height": h, "seed": seed}))
    data = netutil.get_bytes(url, headers={"Authorization": f"Bearer {env['POLLINATIONS_API_KEY']}"}, max_bytes=FULL_MAX)
    return data, cfg["model"]


def _gen_huggingface(prompt, w, h, seed, env):
    cfg = GEN["huggingface"]
    d = netutil.post_json("https://router.huggingface.co/nscale/v1/images/generations",
                          {"response_format": "b64_json", "prompt": prompt, "model": cfg["model"], "size": f"{w}x{h}"},
                          headers={"Authorization": f"Bearer {env['HF_TOKEN']}"})
    try:
        return base64.b64decode(d["data"][0]["b64_json"]), cfg["model"]
    except (KeyError, IndexError, TypeError, ValueError):
        raise netutil.NetError("huggingface: unexpected response (no data[0].b64_json)") from None


def _horde_dict(obj, what):
    if not isinstance(obj, dict):
        raise netutil.NetError(f"horde: unexpected {what} response")
    return obj


def _gen_horde(prompt, w, h, seed, env):
    headers = {"apikey": "0000000000", "Client-Agent": netutil.CLIENT_AGENT}
    w, h = horde_size(w, h)

    def submit(w, h):
        return _horde_dict(netutil.post_json(f"{HORDE}/generate/async", {
            "prompt": prompt, "params": {"width": w, "height": h, "steps": 20, "n": 1, "seed": str(seed)},
            "nsfw": False, "censor_nsfw": True, "r2": True}, headers=headers), "submit")

    try:
        job = submit(w, h)
    except netutil.NetError as e:
        if "HTTP 403" not in str(e):
            raise
        # ponytail: the 403 body (KudosUpfront) is not visible through netutil, so any 403 gets one smaller retry
        w, h = horde_size(w, h, cap=max(64, max(w, h) * 3 // 4))
        job = submit(w, h)
    jid = job.get("id")
    if not isinstance(jid, str) or not jid:
        raise netutil.NetError("horde: submit returned no job id")
    done = False
    try:  # whatever happens after this point (error, 429, Ctrl-C, censored result), do not leave the job queued
        deadline = time.monotonic() + HORDE_TIMEOUT
        while True:
            chk = _horde_dict(netutil.get_json(f"{HORDE}/generate/check/{jid}", headers=headers), "check")
            if chk.get("faulted"):
                raise netutil.NetError("horde: generation faulted")
            if chk.get("is_possible") is False:
                raise netutil.NetError("horde: no worker can serve this request")
            if chk.get("done"):
                break
            if time.monotonic() >= deadline:
                raise netutil.NetError(f"horde: timed out after {HORDE_TIMEOUT}s")
            time.sleep(HORDE_POLL)
        status = _horde_dict(netutil.get_json(f"{HORDE}/generate/status/{jid}", headers=headers), "status")
        gens = status.get("generations")
        gen = gens[0] if isinstance(gens, list) and gens else None
        if not isinstance(gen, dict) or not isinstance(gen.get("img"), str) or not gen["img"]:
            raise netutil.NetError("horde: no image in the result")
        if gen.get("censored"):
            raise netutil.NetError("horde: the image was censored; try a different prompt")
        data = netutil.get_bytes(gen["img"], max_bytes=FULL_MAX)
        done = True
        return data, gen.get("model") or "unknown (AI Horde)"
    finally:
        if not done:
            try:
                netutil.fetch(f"{HORDE}/generate/status/{jid}", headers=headers, method="DELETE")
            except (netutil.NetError, netutil.RateLimited):
                pass


PROVIDERS = {"cloudflare": _gen_cloudflare, "pollinations": _gen_pollinations,
             "huggingface": _gen_huggingface, "horde": _gen_horde}


def _fit(data, w, h):
    """Decode the provider's bytes, center-crop to the w:h aspect and shrink (never enlarge) to at most w x h. -> PIL image."""
    try:
        with Image.open(io.BytesIO(data)) as raw:
            im = raw.convert("RGB")
    except Exception as e:  # noqa: BLE001 - provider returned something that is not an image
        raise netutil.NetError(f"provider returned an unreadable image ({type(e).__name__})") from None
    iw, ih = im.size
    if iw * h > ih * w:  # too wide
        nw = round(ih * w / h)
        im = im.crop(((iw - nw) // 2, 0, (iw - nw) // 2 + nw, ih))
    elif iw * h < ih * w:  # too tall
        nh = round(iw * h / w)
        im = im.crop((0, (ih - nh) // 2, iw, (ih - nh) // 2 + nh))
    if im.width > w:
        im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    return im


def _merge_candidates(out, found):
    """Add new candidate records to candidates.json, keeping earlier ones (photo or generated) with other ids."""
    ids = {c["id"] for c in found}
    kept = [c for c in _load_list(out / "candidates.json") if c.get("id") not in ids]
    images.write_json_atomic(out / "candidates.json", kept + found)


def _summary(c):
    size = f"{c['width']}x{c['height']}" if c.get("width") and c.get("height") else "?x?"
    return f"{c['id']}  {c['source']}  {c['license']}  {size}  {'ai_risk' if c['ai_risk'] else '-'}"


def gen_cmd(a):
    if not 1 <= a.n <= 8:
        print("[assets] --n must be between 1 and 8", file=sys.stderr)
        return 2
    if a.raw:
        final, removed = a.prompt.strip()[:PROMPT_MAX], []
        too_long = len(a.prompt.strip()) > PROMPT_MAX
    else:
        final, removed = clean_prompt(a.prompt)
        too_long = len(_strip_banned(a.prompt)[0]) > PROMPT_MAX - len(GEN["style_suffix"]) - 2  # judged on the cleaned text
    if too_long:
        print(f"[assets] prompt shortened to fit {PROMPT_MAX} characters", file=sys.stderr)
    if removed:
        print(f"[assets] removed from prompt: {', '.join(removed)}", file=sys.stderr)
    if not final:
        print("[assets] the prompt is empty", file=sys.stderr)
        return 2
    if a.provider == "auto":
        chain = [p for p in GEN["order"] if _env(p) is not None]
        if "horde" not in chain:
            chain.append("horde")
        if chain == ["horde"]:
            print("[assets] no image-generation key set: using AI Horde (max 576px, small slots only). For larger "
                  "images (about 1024px) set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN (free).", file=sys.stderr)
    else:
        if _env(a.provider) is None:
            print(f"[assets] {a.provider}: set {', '.join(GEN[a.provider]['needs'])} first", file=sys.stderr)
            return 2
        chain = [a.provider]
    w, h = ASPECTS[a.aspect]
    seed0 = a.seed if a.seed is not None else random.randint(1, 2_000_000_000)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    found, reasons = [], []
    for i in range(a.n):
        seed = seed0 + i
        for provider in list(chain):
            tw, th = (horde_size(w, h) if provider == "horde" else (w, h))
            try:
                data, model = PROVIDERS[provider](final, tw, th, seed, _env(provider))
                im = _fit(data, tw, th)
            except (netutil.RateLimited, netutil.NetError) as e:
                reasons.append(f"{provider}: {e}")
                print(f"[assets] skip {provider}: {e}", file=sys.stderr)
                chain.remove(provider)  # do not keep hitting a provider that just failed
                continue
            fname = f"gen-{provider}-{seed}.png"
            im.save(out / fname)
            found.append({
                "id": f"gen:{provider}:{seed}", "source": f"gen:{provider}", "title": a.prompt.strip(),
                "thumb_file": fname, "full_file": fname, "width": im.width, "height": im.height,
                "author": "AI-generated", "license": GEN[provider]["license"], "attribution_required": False,
                "ai_risk": True, "ai_generated": True, "provider": provider, "model": model, "prompt": final,
                "seed": seed})
            break
        else:
            break  # every provider failed for this image
    if not found:
        print("[assets] image generation failed: " + "; ".join(reasons), file=sys.stderr)
        return 1
    _merge_candidates(out, found)
    for c in found:
        print(_summary(c))
    return 0


def build_parser():
    ap = argparse.ArgumentParser(description="Fetch license-safe assets (photos, icons, AI-generated images) and record credits")
    top = ap.add_subparsers(dest="cmd", required=True)
    photo = top.add_parser("photo").add_subparsers(dest="action", required=True)
    s = photo.add_parser("search")
    s.add_argument("query")
    s.add_argument("--out", required=True)
    s.add_argument("--n", type=int, default=12)
    s.add_argument("--sources")
    s.add_argument("--cache")
    s.set_defaults(fn=photo_search)
    g = photo.add_parser("get")
    g.add_argument("id")
    g.add_argument("--cand", required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--cache")  # caches the Wikimedia 3000px-rendition lookup only; the image download itself is never cached
    g.set_defaults(fn=photo_get)
    ic = top.add_parser("icon").add_subparsers(dest="action", required=True)
    s = ic.add_parser("search")
    s.add_argument("query")
    s.add_argument("--sets")
    s.add_argument("--limit", type=int, default=32)
    s.add_argument("--json", action="store_true")
    s.add_argument("--cache")
    s.set_defaults(fn=icon_search)
    g = ic.add_parser("get")
    g.add_argument("id")
    g.add_argument("--color", required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--size", type=int, default=256)
    g.add_argument("--cache")
    g.set_defaults(fn=icon_get)
    gen = top.add_parser("gen")
    gen.add_argument("prompt")
    gen.add_argument("--out", required=True)
    gen.add_argument("--aspect", choices=sorted(ASPECTS), default="16:9")
    gen.add_argument("--n", type=int, default=2)
    gen.add_argument("--seed", type=int)
    gen.add_argument("--provider", choices=["auto", *PROVIDERS], default="auto")
    gen.add_argument("--raw", action="store_true")
    gen.set_defaults(fn=gen_cmd)
    c = top.add_parser("credits")
    c.add_argument("assets")
    c.add_argument("--lang", choices=("ko", "en"), default="en")
    c.add_argument("--files", action="store_true", help="prefix each line with the file it belongs to")
    c.set_defaults(fn=credits_cmd)
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    sys.exit(main())
