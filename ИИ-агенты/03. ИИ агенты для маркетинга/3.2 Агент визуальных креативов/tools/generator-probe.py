#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Перебор публичных генераторов изображений: какие реально работают.

Проверяет набор публичных Gradio-спейсов Hugging Face: берёт /gradio_api/info,
подставляет промт в подходящий параметр и ждёт результат.

Запуск:  python tools/generator-probe.py
"""
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SPACES = [
    "black-forest-labs/FLUX.1-schnell",
    "multimodalart/FLUX.1-merged",
    "Kwai-Kolors/Kolors",
    "Qwen/Qwen-Image",
    "stabilityai/stable-diffusion-3.5-large-turbo",
    "fffiloni/Stable-Diffusion-CPU",
    "akhaliq/small-stable-diffusion-v0",
    "prodia/fast-stable-diffusion",
    "openskyml/fast-sdxl-stable-diffusion-xl",
    "markmagic/Stable-Diffusion-3-FREE",
    "black-forest-labs/FLUX.1-dev",
    "prithivMLmods/FLUX-LoRA-DLC",
    "ByteDance/SDXL-Lightning",
    "stabilityai/stable-diffusion-xl-base-1.0",
    "hysts/SD-XL",
    "google/sd-turbo",
]

PROMPT = "a red apple on a white table, professional photo"
UA = {"User-Agent": "Mozilla/5.0 (probe)"}


def get(url, timeout=60, data=None, method=None, headers=None):
    h = dict(UA)
    if headers:
        h.update(headers)
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def default_for(p):
    t = (p.get("python_type") or {}).get("type")
    d = p.get("parameter_default")
    if d is not None:
        return d
    if t == "str":
        return ""
    if t == "bool":
        return False
    if t in ("float", "int"):
        return 0
    return None


def probe_space(space):
    sub = space.replace("/", "-").replace(".", "-").replace("_", "-").lower()
    base = "https://%s.hf.space" % sub  # приблизительно; ниже уточним по API
    info = None
    # точный поддомен берём из API
    try:
        meta = json.loads(get("https://huggingface.co/api/spaces/" + space))
        base = meta.get("host") or base
        rt = (meta.get("runtime") or {}).get("hardware", {}).get("current")
    except Exception as e:
        return {"space": space, "error": "meta: %s" % e}

    try:
        info = json.loads(get(base + "/gradio_api/info", timeout=60))
    except Exception as e:
        return {"space": space, "hardware": rt, "error": "info: %s" % e}

    eps = info.get("named_endpoints") or {}
    # ищем эндпоинт с параметром-промтом
    for name, ep in eps.items():
        params = ep.get("parameters") or []
        pnames = [p.get("parameter_name") for p in params]
        if not any(n and "prompt" in n.lower() for n in pnames):
            continue
        data = []
        for p in params:
            n = (p.get("parameter_name") or "").lower()
            if "prompt" in n:
                data.append(PROMPT)
            elif n in ("width", "height") and (p.get("python_type") or {}).get("type") in ("float", "int"):
                data.append(512)
            elif "steps" in n:
                data.append(4)
            elif "seed" in n:
                data.append(0)
            else:
                data.append(default_for(p))
        try:
            r = json.loads(get(base + "/gradio_api/call" + name, timeout=60, data={"data": data}))
            eid = r.get("event_id")
        except urllib.error.HTTPError as e:
            return {"space": space, "hardware": rt, "endpoint": name, "error": "call %s: %s" % (e.code, e.read()[:200])}
        except Exception as e:
            return {"space": space, "hardware": rt, "endpoint": name, "error": "call: %s" % e}
        try:
            sse = get(base + "/gradio_api/call%s/%s" % (name, eid), timeout=300)
        except Exception as e:
            return {"space": space, "hardware": rt, "endpoint": name, "error": "sse: %s" % e}
        m = re.search(r'"url":\s*"([^"]+)"', sse)
        err = re.search(r'event:\s*error', sse)
        return {
            "space": space,
            "hardware": rt,
            "endpoint": name,
            "params": pnames,
            "ok": bool(m),
            "error_event": bool(err),
            "url": m.group(1) if m else None,
            "sse_tail": sse[-200:],
        }
    return {"space": space, "hardware": rt, "error": "нет эндпоинта с промтом", "endpoints": list(eps)}


def main():
    for s in SPACES:
        t0 = time.time()
        res = probe_space(s)
        res["sec"] = round(time.time() - t0, 1)
        print(json.dumps(res, ensure_ascii=False))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
