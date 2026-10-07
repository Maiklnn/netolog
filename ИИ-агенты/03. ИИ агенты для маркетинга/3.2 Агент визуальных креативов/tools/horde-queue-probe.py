#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Быстрый замер: с чего задача реально стартует у анонимного клиента.

Отличие от horde-size-test.py: тот ждёт картинку целиком (до 20 минут на
конфигурацию), а этот только отправляет задания, через 45 секунд снимает
позицию в очереди и отменяет их. Нужен, чтобы выбрать модели для эшелонов
агента, а не измерить одну конкретную пару «размер + модель».

    python tools/horde-queue-probe.py

Проверяется сразу два вопроса:
  • не перегружена ли модель SDXL 1.0 на тяжёлом размере — и не станет ли
    очередь короче, если разрешить Horde выбрать любую из нескольких
    SDXL-моделей (сейчас основной эшелон просит ровно одну);
  • какие 512-нативные модели годятся в лёгкий запас: base-модель
    stable_diffusion в прогоне 86 нарисовала «руки над блокнотом» и куклу
    вместо героини, и её надо заменить на финетюны.

Имена моделей Stable Horde проверяет на отправке: несуществующее имя
возвращается в поле message, поэтому заодно видно, какие имена валидны.
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

PROMPT = ("Realistic commercial photograph, square 1:1. Young professional woman "
          "around 30 in a dark blue blazer sits at a bright desk, laptop open, "
          "speaking mid-sentence into the screen with a confident smile. Soft "
          "diffused window light, palette of dark navy blue, warm orange accent "
          "and light grey air, subject on the right half, large empty area on "
          "the left half, no text, no letters, no watermark, no logo")
NEGATIVE = ("text, letters, numbers, words, watermark, logo, signature, brand "
            "logos, apple logo, laptop logo, flags, maps, extra fingers, fused "
            "fingers, deformed limbs, distorted face, low quality, blurry, "
            "jpeg artifacts, collage, frame")

SDXL_CLASS = ["SDXL 1.0", "Juggernaut XL", "AlbedoBase XL", "DreamShaper XL",
              "ZavyChromaXL"]
NATIVE_512 = ["Realistic Vision", "AbsoluteReality", "epicrealism",
              "CyberRealistic", "Deliberate"]

CONFIGS = [
    ("1024 SDXL 1.0 (как сейчас), 25 шагов", 1024, 1024, ["SDXL 1.0"], 25),
    ("1024 список SDXL-моделей, 25 шагов", 1024, 1024, SDXL_CLASS, 25),
    ("1024 список SDXL-моделей, 30 шагов", 1024, 1024, SDXL_CLASS, 30),
    ("768 список 512-нативных, 30 шагов", 768, 768, NATIVE_512, 30),
    ("512 список 512-нативных, 30 шагов", 512, 512, NATIVE_512, 30),
]


def request(path, body=None, method=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(API + path, data=data, headers=HEADERS,
                                 method=method or ("POST" if data else "GET"))
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def submit(size, models, steps):
    body = {
        "prompt": PROMPT,
        "params": {
            "width": size[0], "height": size[1], "steps": steps,
            "cfg_scale": 7, "sampler_name": "k_euler_a", "n": 1,
            "seed": "777", "negative_prompt": NEGATIVE,
        },
        "nsfw": False, "censor_nsfw": True, "trusted_workers": False,
        "slow_workers": True, "models": models, "r2": False,
    }
    return request("/generate/async", body)


def main():
    jobs = []
    for label, w, h, models, steps in CONFIGS:
        try:
            sub = submit((w, h), models, steps)
        except urllib.error.HTTPError as exc:
            print("%-38s ОТКАЗ %s: %s" % (label, exc.code, exc.read()[:300]))
            continue
        jid = sub.get("id")
        if not jid:
            print("%-38s нет id: %s" % (label, str(sub)[:300]))
            continue
        print("%-38s отправлено id=%s kudos=%s" % (label, jid, sub.get("kudos")))
        jobs.append((label, jid, models))
        time.sleep(1.5)          # анонимному клиенту ~1 запрос в секунду

    if not jobs:
        return 1

    print("\nждём 45 секунд...\n")
    time.sleep(45)

    for label, jid, models in jobs:
        try:
            chk = request("/generate/check/" + jid)
        except Exception as exc:                            # noqa: BLE001
            print("%-38s опрос не удался: %s" % (label, exc))
            continue
        mark = " <-- стартовала" if chk.get("processing") else ""
        print("%-38s очередь=%-5s обработка=%-5s ожидает=%-5s%s"
              % (label, chk.get("queue_position"), chk.get("processing"),
                 chk.get("waiting"), mark))
        if chk.get("faulted"):
            print("     ОТКЛОНЕНО: %s" % str(chk.get("message"))[:300])

    print()
    for label, jid, models in jobs:
        try:
            request("/generate/async/" + jid, None, method="DELETE")
            print("%-38s отменено" % label)
        except Exception as exc:                            # noqa: BLE001
            print("%-38s отменить не удалось: %s" % (label, exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
