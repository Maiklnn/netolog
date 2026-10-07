#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка vision-модели Ollama на уже сгенерированном креативе.

Запускается НА СЕРВЕРЕ n8n (Ollama живёт на 10.0.2.2 и с Windows-хоста
недоступна):

    scp -i C:/Users/MIXA/.ssh/unikor tools/vision-probe.py root@192.168.56.10:/tmp/
    ssh -i C:/Users/MIXA/.ssh/unikor root@192.168.56.10 "python3 /tmp/vision-probe.py /var/lib/n8n/.n8n-files/visual-creatives/images/V1-a1.webp"
"""
import base64
import json
import sys
import time
import urllib.request

IMAGE = sys.argv[1] if len(sys.argv) > 1 else \
    "/var/lib/n8n/.n8n-files/visual-creatives/images/V1-a1.webp"
MODEL = sys.argv[2] if len(sys.argv) > 2 else "deepseek-v4.1-flash:cloud"

PROMPT = ('Посмотри на рекламный креатив и ответь строго JSON без пояснений: '
          '{"text_on_image": true|false, "watermark": true|false, '
          '"comment": "одно короткое предложение по-русски о том, что видно"}')

with open(IMAGE, "rb") as f:
    raw = f.read()
b64 = base64.b64encode(raw).decode()
print("Файл: %s (%d байт, %d символов base64)" % (IMAGE, len(raw), len(b64)))

body = {"model": MODEL, "prompt": PROMPT, "images": [b64], "stream": False,
        "format": "json", "options": {"temperature": 0.1}}

started = time.time()
req = urllib.request.Request("http://10.0.2.2:11434/api/generate",
                             data=json.dumps(body).encode("utf-8"),
                             headers={"Content-Type": "application/json"})
try:
    ans = json.loads(urllib.request.urlopen(req, timeout=600).read())
except Exception as exc:                      # noqa: BLE001
    print("ОШИБКА за %.1f с: %s" % (time.time() - started, exc))
    sys.exit(1)

print("Ответ за %.1f с" % (time.time() - started))
print("done_reason:", ans.get("done_reason"))
print("response:", str(ans.get("response"))[:600])
