#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Выборочный дамп полей узла завершённого (или идущего) прогона.

    python tools/node-dump.py 84 "Собрать промты"
    python tools/node-dump.py 84 "Собрать промты" id prompt_source prompt
    python tools/node-dump.py 84 "Оценка по чек-листу" --all

Зачем отдельный скрипт, если есть inspect-exec.py: тот печатает вывод узла
целиком, и на узле с четырьмя вариантами в этом выводе тонут главные поля
(`prompt_source`, `agent_json_ok`). Здесь печатаются только запрошенные поля,
по одной строке на элемент.

Про данные: в этом n8n результат лежит «уплощённой» таблицей, где ссылки на
вложенные элементы заменены индексами. Разбор берётся из watch-exec.py —
свой уже один раз ошибся и показал пустой runData на живом прогоне.
"""
import importlib.util
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))

# watch-exec.py и n8n-api.py при импорте подменяют sys.stdout своим wrapper'ом;
# без ссылок на прежние потоки их собирает сборщик мусора и закрывает общий
# буфер — печать после этого падает, включая вывод трейсбека.
_keepalive = []


def _pin():
    for stream in (sys.stdout, sys.stderr):
        if not any(stream is s for s in _keepalive):
            _keepalive.append(stream)


_pin()


def load(name):
    _pin()
    spec = importlib.util.spec_from_file_location(name + "_tool", os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _pin()
    return mod


def short(value, limit=200):
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False)
    text = text.replace("\n", " / ")
    return text if len(text) <= limit else text[:limit] + "…"


def main():
    argv = [a for a in sys.argv[1:]]
    if len(argv) < 2:
        sys.exit("использование: python tools/node-dump.py <проверка> <узел> [поля…] [--all]")
    eid, node = argv[0], argv[1]
    want_all = "--all" in argv
    fields = [a for a in argv[2:] if not a.startswith("--")]

    watch = load("watch-exec")
    watch.n8napi.login()
    status, body = watch.n8napi.call("GET", "/rest/executions/%s?includeData=true" % eid)
    if status != 200:
        sys.exit("HTTP %s при чтении прогона %s" % (status, eid))

    data = json.loads(body)["data"]
    table = watch.as_obj(data.get("data")) or []
    if isinstance(table, dict):
        table = [table]
    deref = watch.Deref(table)
    result_data = deref(table[0].get("resultData")) or {}
    run_data = result_data.get("runData") or {}

    runs = run_data.get(node)
    if not runs:
        sys.exit("в прогоне %s нет узла «%s». Есть узлы:\n  %s"
                 % (eid, node, "\n  ".join(sorted(run_data))))

    branch = ((deref(runs[0].get("data")) or {}).get("main") or [[]])[0] or []
    for n, ref in enumerate(branch):
        item = deref(ref)
        js = deref(item.get("json")) if isinstance(item, dict) else None
        if not isinstance(js, dict):
            print("[%d] не объект: %s" % (n, short(js)))
            continue
        keys = sorted(js) if want_all else fields
        print("-" * 70)
        for k in keys:
            if k in js:
                print("  %s: %s" % (k, short(js[k])))
            else:
                print("  %s: (нет поля)" % k)


if __name__ == "__main__":
    main()
