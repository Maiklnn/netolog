#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Выбор моделей для лёгкого эшелона: одна картинка на модель, одним и тем же промтом.

Зачем: в прогоне 86 все четыре креатива вышли лёгким запасом на 512, потому что
тяжёлый размер 1024 у анонимного клиента сейчас закрыт порогом KudosUpfront
(«Due to heavy demand, for requests over 1024x1024 the client needs to already
have the required kudos»). Лёгкий эшелон стал основным путём, и в нём оказалась
base-модель stable_diffusion — она нарисовала «руки над блокнотом» вместо
героини в кадре. Здесь те же условия, что в бою (512x512, 30 шагов, тот же
negative), но по одной модели за раз: видно и качество, и то, что имя модели
существует (несуществующее имя Stable Horde отбивает как faulted).

    python tools/horde-model-pick.py [папка]

Картинки складываются в папку (по умолчанию /tmp/horde-models), её содержимое —
рабочий материал для сравнения, в поставку практики оно не входит.
"""
import io
import json
import os
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

# Промт V1 из прогона 86 — сравниваем модели на одной и той же сцене.
PROMPT = ("Realistic commercial photograph, square 1:1. Young professional woman "
          "around 30 in a dark blue blazer sits at a bright desk, laptop open, "
          "speaking mid-sentence into the screen with a confident smile. Soft "
          "diffused window light, palette of dark navy blue, warm orange accent "
          "and light grey air, minimalist composition, subject on the right half, "
          "large empty area on the left half for text and button, no text, no "
          "letters, no numbers, no words, no watermark, no logo")
NEGATIVE = ("text, letters, numbers, words, captions, watermark, logo, signature, "
            "brand logos, apple logo, laptop logo, device brand marks, flags, "
            "coats of arms, maps, political symbols, children, teenagers, "
            "celebrities, alcohol, weapons, nudity, distorted face, extra fingers, "
            "fused fingers, deformed limbs, low quality, blurry, jpeg artifacts, "
            "collage, frame")

# Кандидаты: 512-нативные финептюны SD 1.5 (первым — тот, что уже стоял, чтобы
# сравнение было честным) и одна тяжёлая SDXL-модель для контроля.
MODELS = ["Realistic Vision", "AbsoluteReality", "CyberRealistic", "epicrealism",
          "Deliberate", "stable_diffusion", "SDXL 1.0"]
SIZE = (512, 512)
STEPS = 30
SEED = "4242"
WAIT_MIN = 12


def request(path, body=None, method=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(API + path, data=data, headers=HEADERS,
                                 method=method or ("POST" if data else "GET"))
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def submit(model):
    return request("/generate/async", {
        "prompt": PROMPT,
        "params": {"width": SIZE[0], "height": SIZE[1], "steps": STEPS,
                   "cfg_scale": 7, "sampler_name": "k_euler_a", "n": 1,
                   "seed": SEED, "negative_prompt": NEGATIVE},
        "nsfw": False, "censor_nsfw": True, "trusted_workers": False,
        "slow_workers": True, "models": [model], "r2": False,
    })


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "/tmp/horde-models"
    os.makedirs(out_dir, exist_ok=True)

    jobs = []
    for model in MODELS:
        try:
            sub = submit(model)
        except urllib.error.HTTPError as exc:
            print("%-18s ОТКАЗ %s: %s" % (model, exc.code, exc.read()[:200]))
            continue
        jid = sub.get("id")
        if not jid:
            print("%-18s нет id: %s" % (model, str(sub)[:200]))
            continue
        print("%-18s отправлено  kudos=%s" % (model, sub.get("kudos")))
        jobs.append([model, jid, None])
        time.sleep(1.5)                    # ~1 запрос в секунду у анонимного клиента

    started = time.time()
    while jobs and time.time() - started < WAIT_MIN * 60:
        time.sleep(15)
        for row in jobs:
            if row[2]:
                continue
            try:
                chk = request("/generate/check/" + row[1])
            except Exception:                                  # noqa: BLE001
                continue
            if chk.get("faulted"):
                row[2] = "ОТКЛОНЕНО"
                print("%-18s ОТКЛОНЕНО: %s" % (row[0], str(chk.get("message"))[:200]))
            elif chk.get("done"):
                st = request("/generate/status/" + row[1])
                gen = (st.get("generations") or [{}])[0]
                img = gen.get("img") or ""
                if not img:
                    row[2] = "пусто"
                    print("%-18s ГОТОВО, но без картинки" % row[0])
                    continue
                path = os.path.join(out_dir, row[0].replace(" ", "_") + ".webp")
                with open(path, "wb") as fh:
                    fh.write(__import__("base64").b64decode(img))
                row[2] = path
                print("%-18s ГОТОВО за %.1f мин  модель=%s  %.1f КБ  -> %s"
                      % (row[0], (time.time() - started) / 60, gen.get("model"),
                         len(img) * 3 / 4 / 1024, path))

    for row in jobs:
        if not row[2]:
            print("%-18s не дождались за %d мин" % (row[0], WAIT_MIN))

    print("\nпапка:", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
