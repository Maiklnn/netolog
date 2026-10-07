#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Замер очереди Stable Horde на боевых конфигурациях агента.

Сколько реально ждать тяжёлый размер (1024x1024, модель SDXL 1.0) и лёгкий
размер на модели, у которой 512 — родное разрешение (SD 1.5-финетюны вроде
Realistic Vision и Deliberate). По замерам видно, стоит ли вообще ждать
1024x1024 у анонимного клиента и не выгоднее ли делать лёгкий запас на
512-нативной модели: SDXL на 512x512 уходит в стилизацию, а SD 1.5 на том же
размере остаётся фотографией.

    python tools/horde-size-test.py            # все задания
    python tools/horde-size-test.py --short    # только 512-нативные

Ничего не печатает из окружения: ключ Stable Horde анонимный и публичный.
"""
import io
import json
import sys
import time
import urllib.error
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace",
                              line_buffering=True)

API = "https://stablehorde.net/api/v2"
HEADERS = {
    "apikey": "0000000000",
    "Client-Agent": "n8n-visual-creatives:1.0:anonymous",
    "Content-Type": "application/json",
}

PROMPT = ("A young professional woman at a tidy home desk with a laptop and "
          "headphones, mid online speaking lesson, warm confident smile, soft "
          "diffused window light, minimalist interior, commercial photography, "
          "no text, no letters, no watermark, no logo")
NEGATIVE = ("text, letters, numbers, words, watermark, logo, signature, "
            "extra fingers, fused fingers, deformed limbs, distorted face, "
            "low quality, blurry, jpeg artifacts, collage, frame")

# Тяжёлый размер: так его отправляет основной эшелон агента.
HEAVY = (1024, 1024, ["SDXL 1.0"], 25)
# Лёгкий запас: маленькая площадь. Слева — на SDXL, справа — на 512-нативной модели.
LIGHT_SDXL = (512, 512, ["SDXL 1.0"], 20)
LIGHT_NATIVE = (512, 512, ["Realistic Vision", "Deliberate", "stable_diffusion"], 25)


def post(path, body):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode("utf-8"),
                                 headers=HEADERS, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def get(path):
    req = urllib.request.Request(API + path, headers=HEADERS)
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def run(label, size, models, steps):
    body = {
        "prompt": PROMPT,
        "params": {
            "width": size[0], "height": size[1], "steps": steps,
            "cfg_scale": 7, "sampler_name": "k_euler_a", "n": 1,
            "seed": "12345", "negative_prompt": NEGATIVE,
        },
        "nsfw": False, "censor_nsfw": True, "trusted_workers": False,
        "slow_workers": True, "models": models, "r2": False,
    }
    started = time.time()
    try:
        sub = post("/generate/async", body)
    except urllib.error.HTTPError as exc:
        print("%-34s ОТКАЗ %s: %s" % (label, exc.code, exc.read()[:200]))
        return None
    job = sub.get("id")
    if not job:
        print("%-34s нет id: %s" % (label, str(sub)[:200]))
        return None
    print("%-34s отправлено  id=%s  kudos=%s" % (label, job, sub.get("kudos")))

    peak = 0
    while time.time() - started < 20 * 60:
        time.sleep(15)
        try:
            chk = get("/generate/check/" + job)
        except Exception:                                   # noqa: BLE001
            continue
        q = chk.get("queue_position")
        if isinstance(q, int):
            peak = max(peak, q)
        if chk.get("faulted"):
            print("%-34s ОТКЛОНЕНО через %.1f мин (модель %s недоступна?)"
                  % (label, (time.time() - started) / 60, models))
            return None
        if chk.get("done"):
            st = get("/generate/status/" + job)
            gen = (st.get("generations") or [{}])[0]
            img = gen.get("img") or ""
            print("%-34s ГОТОВО через %.1f мин  модель=%s  пик очереди=%s  размер=%d КБ"
                  % (label, (time.time() - started) / 60, gen.get("model"), peak,
                     len(img) * 3 // 4 // 1024))
            return (time.time() - started) / 60
    print("%-34s не дождались за 20 мин (пик очереди %s)" % (label, peak))
    return None


def main():
    short = "--short" in sys.argv
    jobs = [("лёгкий 512 SD-модель", LIGHT_NATIVE)]
    if not short:
        jobs = [("тяжёлый 1024 SDXL 1.0", HEAVY),
                ("лёгкий 512 SDXL 1.0", LIGHT_SDXL)] + jobs
    for i, (label, cfg) in enumerate(jobs):
        if i:
            time.sleep(2)                # анонимному клиенту ~1 запрос в секунду
        run(label, (cfg[0], cfg[1]), cfg[2], cfg[3])


if __name__ == "__main__":
    sys.exit(main())
