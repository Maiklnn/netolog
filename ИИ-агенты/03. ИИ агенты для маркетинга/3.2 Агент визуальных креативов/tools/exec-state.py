#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Снимок состояния узлов прогона: какие уже отработали и сколько шли.

    python tools/exec-state.py 83

Отличие от watch-exec.py: тот следит за прогоном в цикле и печатает только
изменения, а этот делает снимок один раз — удобно, когда нужно быстро понять,
на каком узле прогон стоит прямо сейчас.

Разбор данных берётся из watch-exec.py намеренно, а не пишется заново: в этом
n8n результат лежит не в `data.resultData`, а в «уплощённой» таблице, где ссылки
на вложенные элементы заменены индексами (`Deref`). Свой разбор здесь уже один
раз ошибся — показал пустой `runData` на живом прогоне.
"""
import importlib.util
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Оба импортируемых модуля при загрузке делают
#     sys.stdout = io.TextIOWrapper(sys.stdout.buffer, ...)
# Когда второй модуль подменяет поток, wrapper первого остаётся без ссылок, и
# его сборка закрывает ОБЩИЙ буфер. После этого падает любая печать, включая
# вывод трейсбека — процесс молча выходит с кодом 1 («lost sys.stderr»).
# Поэтому держим ссылки на все подменённые потоки: тогда их не собирают.
_keepalive = []


def _pin():
    for stream in (sys.stdout, sys.stderr):
        if not any(stream is s for s in _keepalive):
            _keepalive.append(stream)


_pin()
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def load(name):
    _pin()
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _pin()
    return mod


def main():
    if len(sys.argv) < 2:
        sys.exit("укажите id прогона: python tools/exec-state.py 83")
    eid = sys.argv[1]

    watch = load("watch-exec")
    # Логинимся именно в том экземпляре n8n-api, который загрузил watch-exec:
    # он грузит модуль под своим именем, то есть это отдельный модуль со своей
    # cookie-банкой. Логин в «своём» экземпляре сессию у него не открывает, и
    # запрос данных прогона возвращает 401.
    watch.n8napi.login()

    data, run_data = watch.fetch(eid)
    if data is None:
        sys.exit("не удалось прочитать прогон %s" % eid)

    print("прогон %s | статус: %s | старт: %s"
          % (eid, data.get("status"), data.get("startedAt")))
    if not run_data:
        print("  runData пуст (прогон ещё не записал прогресс)")
        return

    for name, runs in run_data.items():
        if not runs:
            continue
        t = runs[0]
        st = t.get("executionStatus", "?")
        ms = t.get("executionTime", 0) or 0
        mark = "  <-- сейчас" if st == "running" else ""
        print("  %-36s %-10s %8.1f с%s" % (name, st, ms / 1000.0, mark))

    blob = data.get("data")
    if isinstance(blob, dict) and blob.get("error"):
        print("ОШИБКА:", json.dumps(blob["error"], ensure_ascii=False)[:400])


if __name__ == "__main__":
    main()
