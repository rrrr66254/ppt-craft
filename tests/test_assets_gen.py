import base64
import io
import json
import types
import urllib.parse
from pathlib import Path

import pytest
from PIL import Image

import assets
import netutil

FIX = Path(__file__).parent / "fixtures" / "net"
ENV_VARS = ["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN", "POLLINATIONS_API_KEY", "HF_TOKEN"]


def fixture(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def img_bytes(size, fmt="PNG"):
    buf = io.BytesIO()
    Image.new("RGB", size, (100, 120, 140)).save(buf, fmt)
    return buf.getvalue()


@pytest.fixture
def net(monkeypatch):
    """Fake netutil. state['fail'][provider] = exception to raise; every call is recorded in state['calls']."""
    for v in ENV_VARS:
        monkeypatch.delenv(v, raising=False)
    state = {"calls": [], "fail": {}, "checks": 0, "check_done_after": 2, "horde_img": img_bytes((576, 320), "WEBP"),
             "submit_errors": [], "fail_bytes": {}}

    def provider_of(url):
        host = urllib.parse.urlsplit(url).netloc
        return {"api.cloudflare.com": "cloudflare", "gen.pollinations.ai": "pollinations",
                "router.huggingface.co": "huggingface", "aihorde.net": "horde", "r2.example.invalid": "horde"}[host]

    def post_json(url, payload, *, headers=None, timeout=120):
        p = provider_of(url)
        state["calls"].append(("POST", p, url, payload, headers))
        if p in state["fail"]:
            raise state["fail"][p]
        if p == "cloudflare":
            return fixture("cloudflare_gen")
        if p == "huggingface":
            return fixture("hf_gen")
        if state["submit_errors"]:
            raise state["submit_errors"].pop(0)
        return fixture("horde_submit")

    def get_json(url, *, headers=None, cache_dir=None, ttl=86400):
        p = provider_of(url)
        state["calls"].append(("GET", p, url, None, headers))
        if "/generate/check/" in url:
            state["checks"] += 1
            done = fixture("horde_check")
            done["done"] = state["checks"] >= state["check_done_after"]
            return done
        return fixture("horde_status")

    def get_bytes(url, *, headers=None, timeout=60, max_bytes=50_000_000):
        p = provider_of(url)
        state["calls"].append(("BYTES", p, url, None, headers))
        if p in state["fail_bytes"]:
            raise state["fail_bytes"][p]
        if p == "pollinations":  # the real service honours width/height
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            return img_bytes((int(q["width"][0]), int(q["height"][0])))
        return state["horde_img"]

    def fetch(url, *, headers=None, timeout=30, data=None, method=None, max_bytes=None):
        state["calls"].append((method or "GET", provider_of(url), url, None, headers))
        return b"{}"

    monkeypatch.setattr(netutil, "post_json", post_json)
    monkeypatch.setattr(netutil, "get_json", get_json)
    monkeypatch.setattr(netutil, "get_bytes", get_bytes)
    monkeypatch.setattr(netutil, "fetch", fetch)
    state["sleeps"] = []
    clock = [0.0]

    def sleep(s):
        state["sleeps"].append(s)
        clock[0] += s

    monkeypatch.setattr(assets, "time", types.SimpleNamespace(sleep=sleep, monotonic=lambda: clock[0]))
    return state


def gen(tmp_path, *extra, prompt="a red squirrel in a forest"):
    return assets.main(["gen", prompt, "--out", str(tmp_path / "assets" / "_cand"), "--seed", "100", *extra])


def cands(tmp_path):
    return json.loads((tmp_path / "assets" / "_cand" / "candidates.json").read_text(encoding="utf-8"))


def set_cloudflare(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok456")


# ---------- prompt hygiene ----------

def test_clean_prompt_removes_banned_words_and_appends_suffix():
    final, removed = assets.clean_prompt("A Cinematic ultra-detailed 8K photo of a squirrel, neon glow, hyper-realistic")
    assert removed == ["8k", "ultra-detailed", "hyper-realistic", "cinematic", "neon"]
    assert final == f"A photo of a squirrel, glow, {assets.GEN['style_suffix']}"
    for w in assets.GEN["banned_words"]:
        assert w not in final.lower().replace(assets.GEN["style_suffix"], "")


def test_clean_prompt_whole_words_only():
    final, removed = assets.clean_prompt("a neonatal ward, glossy-eyed octane pump")
    assert removed == ["octane"] and "neonatal" in final and "glossy-eyed" in final


def test_cli_hygiene_message_and_stored_prompts(net, tmp_path, capsys):
    assert gen(tmp_path, "--n", "1", prompt="cinematic squirrel, 8k") == 0
    assert "[assets] removed from prompt: 8k, cinematic" in capsys.readouterr().err
    rec = cands(tmp_path)[0]
    assert rec["title"] == "cinematic squirrel, 8k"  # the user prompt
    assert rec["prompt"] == f"squirrel, {assets.GEN['style_suffix']}"  # the final prompt
    assert net["calls"][0][3]["prompt"] == rec["prompt"]


def test_raw_keeps_prompt_verbatim(net, tmp_path, capsys):
    assert gen(tmp_path, "--n", "1", "--raw", prompt="cinematic squirrel, 8k") == 0
    assert "removed from prompt" not in capsys.readouterr().err
    rec = cands(tmp_path)[0]
    assert rec["prompt"] == "cinematic squirrel, 8k" and net["calls"][0][3]["prompt"] == "cinematic squirrel, 8k"


def test_empty_prompt_after_cleaning_exits_2(net, tmp_path):
    assert gen(tmp_path, prompt="8k, neon") == 2
    assert not net["calls"]


# ---------- provider selection ----------

def test_auto_picks_cloudflare_when_configured(net, tmp_path, monkeypatch, capsys):
    set_cloudflare(monkeypatch)
    assert gen(tmp_path, "--n", "1") == 0
    kind, prov, url, payload, headers = net["calls"][0]
    assert prov == "cloudflare" and url == ("https://api.cloudflare.com/client/v4/accounts/acct123/ai/run/"
                                           "@cf/black-forest-labs/flux-1-schnell")
    assert headers == {"Authorization": "Bearer tok456"}
    assert payload == {"prompt": payload["prompt"], "steps": 4, "seed": 100}
    assert "AI Horde" not in capsys.readouterr().err
    rec = cands(tmp_path)[0]
    assert rec["id"] == "gen:cloudflare:100" and rec["source"] == "gen:cloudflare" and rec["license"] == "Apache-2.0"
    assert rec["model"] == "@cf/black-forest-labs/flux-1-schnell"


def test_cloudflare_square_output_is_center_cropped_to_aspect(net, tmp_path):
    for aspect, ratio in (("16:9", 16 / 9), ("4:3", 4 / 3), ("3:2", 3 / 2), ("1:1", 1.0)):
        im = assets._fit(img_bytes((128, 128), "JPEG"), *assets.ASPECTS[aspect])
        assert im.width / im.height == pytest.approx(ratio, abs=0.03) and im.width <= assets.ASPECTS[aspect][0]
    big = assets._fit(img_bytes((3000, 3000)), 1344, 768)  # shrinks, never enlarges
    assert big.size == (1344, 768)
    small = assets._fit(img_bytes((100, 100)), 1344, 768)
    assert small.size == (100, 57)  # 1344x768 is 7:4


def test_auto_without_keys_uses_horde_with_warning(net, tmp_path, capsys):
    assert gen(tmp_path, "--n", "1") == 0
    err = capsys.readouterr().err
    assert ("[assets] no image-generation key set: using AI Horde (max 576px, small slots only). For larger images "
            "(about 1024px) set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN (free).") in err
    assert {c[1] for c in net["calls"]} == {"horde"}
    assert cands(tmp_path)[0]["source"] == "gen:horde"


def test_provider_flag_requires_its_env(net, tmp_path, capsys):
    assert gen(tmp_path, "--provider", "cloudflare") == 2
    assert "CLOUDFLARE_ACCOUNT_ID" in capsys.readouterr().err
    assert not net["calls"]
    with pytest.raises(SystemExit) as e:  # argparse choices
        gen(tmp_path, "--provider", "nope")
    assert e.value.code == 2


def test_cloudflare_rate_limited_falls_through_to_next_available(net, tmp_path, monkeypatch, capsys):
    set_cloudflare(monkeypatch)
    monkeypatch.setenv("POLLINATIONS_API_KEY", "pk")
    net["fail"]["cloudflare"] = netutil.RateLimited("api.cloudflare.com: rate limited")
    assert gen(tmp_path, "--n", "2") == 0
    err = capsys.readouterr().err
    assert "[assets] skip cloudflare: api.cloudflare.com: rate limited" in err
    assert [r["source"] for r in cands(tmp_path)] == ["gen:pollinations", "gen:pollinations"]
    assert sum(c[1] == "cloudflare" for c in net["calls"]) == 1  # not retried for the second image


def test_fall_through_to_horde_last_and_all_failed_exit_1(net, tmp_path, monkeypatch, capsys):
    set_cloudflare(monkeypatch)
    net["fail"]["cloudflare"] = netutil.NetError("cf -> HTTP 500")
    assert gen(tmp_path, "--n", "1") == 0
    assert cands(tmp_path)[0]["source"] == "gen:horde"
    net["fail"]["horde"] = netutil.NetError("horde -> HTTP 503")
    assert gen(tmp_path, "--n", "1", "--seed", "5") == 1
    err = capsys.readouterr().err
    assert "[assets] image generation failed: cloudflare: api.cloudflare.com -> HTTP 500; horde: horde -> HTTP 503" in err


def test_unreadable_provider_image_falls_through(net, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("POLLINATIONS_API_KEY", "pk")
    monkeypatch.setattr(netutil, "get_bytes", lambda url, **kw: b"<html>402</html>" if "pollinations" in url else img_bytes((576, 320)))
    assert gen(tmp_path, "--n", "1") == 0
    assert "skip pollinations: provider returned an unreadable image" in capsys.readouterr().err
    assert cands(tmp_path)[0]["source"] == "gen:horde"


def test_pollinations_request_shape(net, tmp_path, monkeypatch):
    monkeypatch.setenv("POLLINATIONS_API_KEY", "pk")
    assert gen(tmp_path, "--n", "1", "--aspect", "4:3") == 0
    kind, prov, url, _, headers = net["calls"][0]
    parts = urllib.parse.urlsplit(url)
    assert parts.netloc == "gen.pollinations.ai" and parts.path.startswith("/image/a%20red%20squirrel")
    assert urllib.parse.parse_qs(parts.query) == {"model": ["black-forest-labs/flux.1-schnell"], "width": ["1152"],
                                                  "height": ["864"], "seed": ["100"]}
    assert headers == {"Authorization": "Bearer pk"}
    assert cands(tmp_path)[0]["width"] == 1152


def test_huggingface_request_shape(net, tmp_path, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_x")
    assert gen(tmp_path, "--n", "1", "--provider", "huggingface", "--aspect", "3:2") == 0
    kind, prov, url, payload, headers = net["calls"][0]
    assert url == "https://router.huggingface.co/nscale/v1/images/generations"
    assert payload["model"] == "black-forest-labs/FLUX.1-schnell" and payload["size"] == "1216x800"
    assert payload["response_format"] == "b64_json" and headers == {"Authorization": "Bearer hf_x"}
    assert cands(tmp_path)[0]["source"] == "gen:huggingface"


def test_unexpected_cloudflare_response_falls_through(net, tmp_path, monkeypatch, capsys):
    set_cloudflare(monkeypatch)
    real = netutil.post_json
    monkeypatch.setattr(netutil, "post_json",
                        lambda url, payload, **kw: {"success": False, "errors": [{"message": "x"}]} if "cloudflare" in url
                        else real(url, payload, **kw))
    assert gen(tmp_path, "--n", "1") == 0
    assert "skip cloudflare: cloudflare: unexpected response" in capsys.readouterr().err


# ---------- horde ----------

def test_horde_flow_submit_check_check_status_download(net, tmp_path):
    assert gen(tmp_path, "--n", "1") == 0
    calls = [(c[0], c[1], urllib.parse.urlsplit(c[2]).path) for c in net["calls"]]
    jid = fixture("horde_submit")["id"]
    assert calls == [("POST", "horde", "/api/v2/generate/async"),
                     ("GET", "horde", f"/api/v2/generate/check/{jid}"),
                     ("GET", "horde", f"/api/v2/generate/check/{jid}"),
                     ("GET", "horde", f"/api/v2/generate/status/{jid}"),
                     ("BYTES", "horde", "/horde/abc.webp")]
    assert net["sleeps"] == [3]  # slept once between the two checks
    post = net["calls"][0]
    assert post[4]["apikey"] == "0000000000" and post[4]["Client-Agent"].startswith("ppt-craft:")
    body = post[3]
    assert body["params"] == {"width": 576, "height": 320, "steps": 20, "n": 1, "seed": "100"}
    assert (body["nsfw"], body["censor_nsfw"], body["r2"]) == (False, True, True)
    rec = cands(tmp_path)[0]
    assert rec["model"] == "stable_diffusion" and rec["license"] == "unverified (per-model)"
    assert (rec["width"], rec["height"]) == (576, 320)
    assert (tmp_path / "assets" / "_cand" / "gen-horde-100.png").exists()


@pytest.mark.parametrize("aspect", sorted(assets.ASPECTS))
def test_horde_size_cap(aspect):
    w, h = assets.horde_size(*assets.ASPECTS[aspect])
    assert max(w, h) <= 576 and w % 64 == 0 and h % 64 == 0 and min(w, h) >= 64
    tw, th = assets.ASPECTS[aspect]
    assert w / h == pytest.approx(tw / th, rel=0.2)


def test_horde_size_values():
    assert assets.horde_size(1344, 768) == (576, 320)
    assert assets.horde_size(1024, 1024) == (576, 576)
    assert assets.horde_size(512, 320) == (512, 320)  # already small: unchanged


def test_horde_request_uses_capped_size_for_16_9(net, tmp_path):
    assert gen(tmp_path, "--n", "1", "--aspect", "16:9") == 0
    p = net["calls"][0][3]["params"]
    assert max(p["width"], p["height"]) <= 576


def test_horde_timeout_deletes_job_and_fails(net, tmp_path, capsys):
    net["check_done_after"] = 10 ** 9
    assert gen(tmp_path, "--n", "1") == 1
    assert "horde: timed out after 180s" in capsys.readouterr().err
    assert ("DELETE", "horde", f"https://aihorde.net/api/v2/generate/status/{fixture('horde_submit')['id']}") in [
        (c[0], c[1], c[2]) for c in net["calls"]]
    assert sum(net["sleeps"]) >= 180 and not (tmp_path / "assets" / "_cand" / "candidates.json").exists()


def test_horde_403_retries_once_smaller(net, tmp_path):
    net["submit_errors"] = [netutil.NetError("https://aihorde.net/api/v2/generate/async -> HTTP 403")]
    assert gen(tmp_path, "--n", "1") == 0
    posts = [c[3]["params"] for c in net["calls"] if c[0] == "POST"]
    assert len(posts) == 2 and posts[1]["width"] < posts[0]["width"]
    assert posts[1]["width"] % 64 == 0 and posts[1]["height"] % 64 == 0


def test_horde_403_twice_fails(net, tmp_path, capsys):
    net["submit_errors"] = [netutil.NetError("x -> HTTP 403")] * 2
    assert gen(tmp_path, "--n", "1") == 1
    assert "HTTP 403" in capsys.readouterr().err


def test_horde_censored_result_is_rejected(net, tmp_path, monkeypatch, capsys):
    status = fixture("horde_status")
    status["generations"][0]["censored"] = True
    real = netutil.get_json
    monkeypatch.setattr(netutil, "get_json", lambda url, **kw: status if "/status/" in url else real(url, **kw))
    assert gen(tmp_path, "--n", "1") == 1
    assert "censored" in capsys.readouterr().err


def test_horde_faulted_job_fails(net, tmp_path, monkeypatch, capsys):
    real = netutil.get_json
    monkeypatch.setattr(netutil, "get_json",
                        lambda url, **kw: dict(fixture("horde_check"), faulted=True) if "/check/" in url else real(url, **kw))
    assert gen(tmp_path, "--n", "1") == 1
    assert "faulted" in capsys.readouterr().err


# ---------- output, merge, get, credits ----------

def test_n_images_use_consecutive_seeds(net, tmp_path, monkeypatch):
    set_cloudflare(monkeypatch)
    assert gen(tmp_path, "--n", "3") == 0
    assert [r["id"] for r in cands(tmp_path)] == ["gen:cloudflare:100", "gen:cloudflare:101", "gen:cloudflare:102"]
    for s in (100, 101, 102):
        assert (tmp_path / "assets" / "_cand" / f"gen-cloudflare-{s}.png").exists()


def test_stdout_summary_line(net, tmp_path, monkeypatch, capsys):
    set_cloudflare(monkeypatch)
    gen(tmp_path, "--n", "1")
    assert capsys.readouterr().out.strip() == "gen:cloudflare:100  gen:cloudflare  Apache-2.0  128x73  ai_risk"


def test_candidates_merge_keeps_photo_candidates(net, tmp_path, monkeypatch):
    cand = tmp_path / "assets" / "_cand"
    cand.mkdir(parents=True)
    photo = {"id": "wikimedia:1", "source": "wikimedia", "title": "T", "thumb_file": "wikimedia_1.jpg"}
    (cand / "candidates.json").write_text(json.dumps([photo]), encoding="utf-8")
    set_cloudflare(monkeypatch)
    assert gen(tmp_path, "--n", "1") == 0
    assert gen(tmp_path, "--n", "1") == 0  # same seed again: replaced, not duplicated
    ids = [r["id"] for r in cands(tmp_path)]
    assert ids == ["wikimedia:1", "gen:cloudflare:100"]


def test_candidate_record_has_all_fields(net, tmp_path, monkeypatch):
    set_cloudflare(monkeypatch)
    gen(tmp_path, "--n", "1")
    rec = cands(tmp_path)[0]
    assert rec == {"id": "gen:cloudflare:100", "source": "gen:cloudflare", "title": "a red squirrel in a forest",
                   "thumb_file": "gen-cloudflare-100.png", "full_file": "gen-cloudflare-100.png", "width": 128,
                   "height": 73, "author": "AI-generated", "license": "Apache-2.0", "attribution_required": False,
                   "ai_risk": True, "ai_generated": True, "provider": "cloudflare",
                   "model": "@cf/black-forest-labs/flux-1-schnell",
                   "prompt": f"a red squirrel in a forest, {assets.GEN['style_suffix']}", "seed": 100}


def get(tmp_path, cid):
    return assets.main(["photo", "get", cid, "--cand", str(tmp_path / "assets" / "_cand"), "--out", str(tmp_path / "assets")])


def test_photo_get_copies_local_file_and_writes_ai_credit(net, tmp_path, monkeypatch, capsys):
    set_cloudflare(monkeypatch)
    gen(tmp_path, "--n", "1")
    n_calls = len(net["calls"])
    capsys.readouterr()
    assert get(tmp_path, "gen:cloudflare:100") == 0
    assert len(net["calls"]) == n_calls  # nothing downloaded
    out = tmp_path / "assets"
    name = capsys.readouterr().out.strip()
    assert name.startswith("gen-cloudflare-100") and (out / name).exists()
    assert name in json.loads((out / "images.json").read_text(encoding="utf-8"))
    rec = json.loads((out / "credits.json").read_text(encoding="utf-8"))[0]
    assert rec["file"] == name and rec["ai_generated"] is True and rec["provider"] == "cloudflare"
    assert rec["model"] == "@cf/black-forest-labs/flux-1-schnell" and rec["seed"] == 100
    assert rec["prompt"].endswith(assets.GEN["style_suffix"]) and rec["license"] == "Apache-2.0"
    assert rec["attribution_required"] is False and rec["ai_risk"] is True and rec["source"] == "gen:cloudflare"
    assert rec["low_res"] is True  # 128px test image is far below generate.min_width


def test_photo_get_gen_missing_file_exits_1(net, tmp_path, monkeypatch, capsys):
    set_cloudflare(monkeypatch)
    gen(tmp_path, "--n", "1")
    (tmp_path / "assets" / "_cand" / "gen-cloudflare-100.png").unlink()
    assert get(tmp_path, "gen:cloudflare:100") == 1
    assert "cannot read the generated image" in capsys.readouterr().err


def test_credits_prints_ai_disclosure(net, tmp_path, monkeypatch, capsys):
    set_cloudflare(monkeypatch)
    gen(tmp_path, "--n", "1")
    get(tmp_path, "gen:cloudflare:100")
    capsys.readouterr()
    assets.main(["credits", str(tmp_path / "assets"), "--lang", "en"])
    assert capsys.readouterr().out.splitlines() == ["  AI-generated image (FLUX.1-schnell via Cloudflare Workers AI)"]
    assets.main(["credits", str(tmp_path / "assets"), "--lang", "ko"])
    assert capsys.readouterr().out.splitlines() == ["  AI 생성 이미지 (FLUX.1-schnell, Cloudflare Workers AI)"]


def test_bad_usage_exits_2(net, tmp_path):
    assert gen(tmp_path, "--n", "0") == 2
    with pytest.raises(SystemExit) as e:
        gen(tmp_path, "--aspect", "21:9")
    assert e.value.code == 2


# ---------- review fixes ----------

def test_banned_words_caught_next_to_korean_text():
    final, removed = assets.clean_prompt("cinematic한 사진, 8k화질 책상, hyper realistic desk, ultra detailed")
    assert removed == ["8k", "hyper realistic", "ultra detailed", "cinematic"]
    assert "cinematic" not in final and "8k" not in final.lower().split(assets.GEN["style_suffix"])[0]
    assert "사진" in final and "책상" in final


def test_banned_words_still_spare_hyphenated_and_longer_words():
    final, removed = assets.clean_prompt("neonatal ward, glossy-eyed octane8 pump")
    assert removed == [] and "neonatal" in final and "glossy-eyed" in final and "octane8" in final


def test_n_is_capped_1_to_8(net, tmp_path):
    assert gen(tmp_path, "--n", "9") == 2 and gen(tmp_path, "--n", "0") == 2
    assert not net["calls"]
    assert gen(tmp_path, "--n", "1") == 0


def test_long_prompt_is_cut_once_keeping_suffix_and_stored_as_sent(net, tmp_path, monkeypatch, capsys):
    set_cloudflare(monkeypatch)
    assert gen(tmp_path, "--n", "1", prompt="squirrel " * 400) == 0
    sent = net["calls"][0][3]["prompt"]
    rec = cands(tmp_path)[0]
    assert len(sent) <= 2048 and sent.endswith(assets.GEN["style_suffix"]) and rec["prompt"] == sent
    assert "prompt shortened" in capsys.readouterr().err
    assert gen(tmp_path, "--n", "1", "--raw", "--seed", "7", prompt="x" * 3000) == 0
    assert len(net["calls"][-1][3]["prompt"]) == 2048


def test_shortened_notice_is_judged_on_cleaned_text(net, tmp_path, monkeypatch, capsys):
    set_cloudflare(monkeypatch)
    assert gen(tmp_path, "--n", "1", prompt="neon " * 500 + "squirrel") == 0  # 2500+ chars, but 8 once banned words are gone
    err = capsys.readouterr().err
    assert "removed from prompt: neon" in err and "prompt shortened" not in err


def test_cloudflare_errors_do_not_leak_the_account_id(net, tmp_path, monkeypatch, capsys):
    set_cloudflare(monkeypatch)
    net["fail"]["cloudflare"] = netutil.NetError(
        "https://api.cloudflare.com/client/v4/accounts/acct123/ai/run/@cf/black-forest-labs/flux-1-schnell -> HTTP 401")
    assert gen(tmp_path, "--n", "1") == 0  # falls through to horde
    err = capsys.readouterr().err
    assert "acct123" not in err and "skip cloudflare: api.cloudflare.com -> HTTP 401" in err


def test_ai_labels_fall_back_to_record_values():
    assert assets._ai_labels({"provider": "horde", "model": "stable_diffusion"}) == ("stable_diffusion", "AI Horde")
    assert assets._ai_labels({"provider": "pollinations", "model": "x"}) == ("FLUX.1-schnell", "Pollinations")
    assert assets._ai_labels({"provider": "huggingface"}) == ("FLUX.1-schnell", "Hugging Face (nscale)")
    assert assets._ai_labels({"provider": "mystery", "model": "m"}) == ("m", "mystery")
    assert assets._ai_labels({}) == ("unknown", "unknown")


def deletes(net):
    return [c for c in net["calls"] if c[0] == "DELETE"]


def test_horde_poll_failure_deletes_the_job(net, tmp_path, monkeypatch):
    real = netutil.get_json

    def flaky(url, **kw):
        if "/check/" in url:
            raise netutil.NetError("horde -> HTTP 500")
        return real(url, **kw)

    monkeypatch.setattr(netutil, "get_json", flaky)
    assert gen(tmp_path, "--n", "1") == 1
    assert len(deletes(net)) == 1 and deletes(net)[0][2].endswith(f"/generate/status/{fixture('horde_submit')['id']}")


def test_horde_rate_limited_poll_deletes_the_job(net, tmp_path, monkeypatch):
    real = netutil.get_json

    def limited(url, **kw):
        if "/check/" in url:
            raise netutil.RateLimited("aihorde.net: rate limited")
        return real(url, **kw)

    monkeypatch.setattr(netutil, "get_json", limited)
    assert gen(tmp_path, "--n", "1") == 1 and len(deletes(net)) == 1


def test_horde_image_download_failure_deletes_the_job(net, tmp_path):
    net["fail_bytes"]["horde"] = netutil.NetError("r2 -> HTTP 404")  # the image download fails after the job is done
    assert gen(tmp_path, "--n", "1") == 1 and len(deletes(net)) == 1


def test_horde_censored_result_deletes_the_job(net, tmp_path, monkeypatch):
    status = fixture("horde_status")
    status["generations"][0]["censored"] = True
    real = netutil.get_json
    monkeypatch.setattr(netutil, "get_json", lambda url, **kw: status if "/status/" in url else real(url, **kw))
    assert gen(tmp_path, "--n", "1") == 1 and len(deletes(net)) == 1


def test_horde_keyboard_interrupt_deletes_the_job(net, tmp_path, monkeypatch):
    def interrupt(url, **kw):
        raise KeyboardInterrupt

    monkeypatch.setattr(netutil, "get_json", interrupt)
    with pytest.raises(KeyboardInterrupt):
        gen(tmp_path, "--n", "1")
    assert len(deletes(net)) == 1


def test_horde_success_sends_no_delete_and_timeout_exactly_one(net, tmp_path):
    assert gen(tmp_path, "--n", "1") == 0 and deletes(net) == []
    net["check_done_after"] = 10 ** 9
    assert gen(tmp_path, "--n", "1", "--seed", "9") == 1
    assert len(deletes(net)) == 1  # once, not twice


def test_horde_delete_failure_is_ignored(net, tmp_path, monkeypatch, capsys):
    net["check_done_after"] = 10 ** 9

    def fetch(url, **kw):
        raise netutil.NetError("delete failed")

    monkeypatch.setattr(netutil, "fetch", fetch)
    assert gen(tmp_path, "--n", "1") == 1
    assert "timed out" in capsys.readouterr().err


def test_horde_no_worker_possible_fails_fast(net, tmp_path, monkeypatch, capsys):
    real = netutil.get_json
    monkeypatch.setattr(netutil, "get_json",
                        lambda url, **kw: dict(fixture("horde_check"), is_possible=False) if "/check/" in url else real(url, **kw))
    assert gen(tmp_path, "--n", "1") == 1
    assert "horde: no worker can serve this request" in capsys.readouterr().err
    assert net["sleeps"] == [] and len(deletes(net)) == 1


@pytest.mark.parametrize("bad_submit", [{}, {"id": ""}, {"id": 5}, [], "oops", None, {"message": "queue full"}])
def test_horde_malformed_submit_is_a_net_error_not_a_traceback(net, tmp_path, monkeypatch, capsys, bad_submit):
    real = netutil.post_json
    monkeypatch.setattr(netutil, "post_json",
                        lambda url, payload, **kw: bad_submit if "aihorde" in url else real(url, payload, **kw))
    assert gen(tmp_path, "--n", "1") == 1
    assert "[assets] skip horde: horde:" in capsys.readouterr().err
    assert deletes(net) == []  # there is no job to delete


@pytest.mark.parametrize("path,bad", [("/check/", []), ("/check/", None), ("/status/", []), ("/status/", {"generations": "x"}),
                                      ("/status/", {"generations": [None]}), ("/status/", {"generations": [{"img": None}]}),
                                      ("/status/", {"generations": []})])
def test_horde_malformed_check_status_are_net_errors(net, tmp_path, monkeypatch, capsys, path, bad):
    real = netutil.get_json
    monkeypatch.setattr(netutil, "get_json", lambda url, **kw: bad if path in url else real(url, **kw))
    assert gen(tmp_path, "--n", "1") == 1
    assert "[assets] skip horde: horde:" in capsys.readouterr().err and len(deletes(net)) == 1


def _cand(tmp_path, width):
    cand = tmp_path / "assets" / "_cand"
    cand.mkdir(parents=True)
    (cand / "g.png").write_bytes(img_bytes((width, width // 2)))
    rec = {"id": "gen:cloudflare:1", "source": "gen:cloudflare", "title": "t", "thumb_file": "g.png", "full_file": "g.png",
           "width": width, "height": width // 2, "author": "AI-generated", "license": "Apache-2.0",
           "attribution_required": False, "ai_risk": True, "ai_generated": True, "provider": "cloudflare",
           "model": "m", "prompt": "p", "seed": 1}
    (cand / "candidates.json").write_text(json.dumps([rec]), encoding="utf-8")
    return cand


@pytest.mark.parametrize("width, low", [(1024, False), (576, True)])
def test_photo_get_gen_low_res_uses_generate_min_width(tmp_path, width, low):
    cand = _cand(tmp_path, width)
    assert assets.main(["photo", "get", "gen:cloudflare:1", "--cand", str(cand), "--out", str(tmp_path / "assets")]) == 0
    rec = json.loads((tmp_path / "assets" / "credits.json").read_text(encoding="utf-8"))[0]
    assert rec.get("low_res", False) is low
