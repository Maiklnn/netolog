#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Выгрузка результатов агента с сервера n8n в локальную папку проекта.

Забирает картинки в `creatives/` и отчёты (`registry.json` / `.csv` / `.md`)
в `result/`, после чего их берёт `tools/fill-template.py`.

Запуск:  python tools/fetch-results.py
"""
import io
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = "root@192.168.56.10"
KEY = "C:/Users/MIXA/.ssh/unikor"
REMOTE = "/var/lib/n8n/.n8n-files/visual-creatives"
CREATIVES = os.path.join(HERE, "creatives")
RESULT = os.path.join(HERE, "result")

SSH = ["ssh", "-i", KEY, "-o", "StrictHostKeyChecking=no"]
SCP = ["scp", "-i", KEY, "-o", "StrictHostKeyChecking=no", "-r"]


def run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        sys.exit("команда не выполнилась: %s\n%s" % (" ".join(cmd), proc.stderr.strip()))
    return proc.stdout


def main():
    os.makedirs(CREATIVES, exist_ok=True)
    os.makedirs(RESULT, exist_ok=True)

    names = run(SSH + [HOST, "ls -1 %s/images/" % REMOTE]).split()
    if not names:
        sys.exit("на сервере нет картинок: %s/images/ пуста" % REMOTE)

    run(SCP + ["%s:%s/images/*" % (HOST, REMOTE), CREATIVES + "/"])
    for report in ("registry.json", "registry.csv", "registry.md"):
        run(SCP + ["%s:%s/%s" % (HOST, REMOTE, report), RESULT + "/"])
    # бриф тоже лежит на сервере — держим локальную копию в актуальном виде
    run(SCP + ["%s:%s/brief.json" % (HOST, REMOTE), HERE + "/"])

    print("Картинок: %d -> %s" % (len(names), CREATIVES))
    for name in sorted(names):
        print("   ", name)
    print("Отчёты -> %s" % RESULT)


if __name__ == "__main__":
    main()
