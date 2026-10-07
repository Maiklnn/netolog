#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка моделей Ollama на роль агента-промт-инженера.

Гоняет НАСТОЯЩИЙ системный промт агента и НАСТОЯЩИЙ вход (brief_pack) по
нескольким моделям и показывает, кто возвращает разбираемый JSON, а кто —
прозу. Запускается на сервере n8n: Ollama живёт на 10.0.2.2 и с Windows-хоста
недоступна.

    scp -i C:/Users/MIXA/.ssh/unikor tools/00-agent-system.md root@192.168.56.10:/tmp/agent-system.md
    scp -i C:/Users/MIXA/.ssh/unikor tools/fixtures/brief-pack.txt root@192.168.56.10:/tmp/brief_pack.txt
    scp -i C:/Users/MIXA/.ssh/unikor tools/agent-model-probe.py root@192.168.56.10:/tmp/
    ssh -i C:/Users/MIXA/.ssh/unikor root@192.168.56.10 "python3 /tmp/agent-model-probe.py"

Вывод на боевом брифе (30.09.2026): deepseek-v4.1-flash:cloud даёт валидный JSON
за ~14 с, glm-5.2:cloud — за ~25 с, gemma4:31b-cloud отвечает JSON в markdown-
обёртке (узел её снимает), qwen2.5-coder:7b работает локально, но ~93 с.
"""
import json
import sys
import time
import urllib.request

SYSTEM = "/tmp/agent-system.md"
BRIEF = "/tmp/brief_pack.txt"
MODELS = [
    "deepseek-v4.1-flash:cloud",
    "glm-5.2:cloud",
    "gemma4:31b-cloud",
    "qwen2.5-coder:7b",
]


def extract_json(text):
    """Тот же разбор, что в узле «Собрать промты»: снимаем ```-обёртку."""
    cleaned = text.replace("```json", "```").replace("```", "\n")
    a, b = cleaned.find("{"), cleaned.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        return json.loads(cleaned[a:b + 1])
    except ValueError:
        return None


def main():
    system = open(SYSTEM, encoding="utf-8").read().strip()
    brief = open(BRIEF, encoding="utf-8").read()

    for model in MODELS:
        body = {
            "model": model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.4},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": brief}],
        }
        started = time.time()
        try:
            req = urllib.request.Request(
                "http://10.0.2.2:11434/api/chat",
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"})
            ans = json.loads(urllib.request.urlopen(req, timeout=600).read())
        except Exception as exc:                       # noqa: BLE001
            print("%-26s ОШИБКА за %.1f с: %s" % (model, time.time() - started, exc))
            continue

        text = str(ans.get("message", {}).get("content") or "")
        parsed = extract_json(text)
        ids = []
        if isinstance(parsed, dict) and isinstance(parsed.get("variants"), list):
            ids = [v.get("id") for v in parsed["variants"]]
        print("%-26s %6.1f с  JSON=%s  варианты=%s  длина=%d  done_reason=%s"
              % (model, time.time() - started, bool(ids), ids, len(text),
                 ans.get("done_reason")))
        if not ids:
            print("      начало ответа: %s" % text[:220].replace("\n", " / "))


if __name__ == "__main__":
    sys.exit(main())
