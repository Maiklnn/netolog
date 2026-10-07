#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Разбор данных конкретного запуска n8n: что вернул каждый узел.

Длинные значения (base64 картинок) обрезаются, чтобы не забивать вывод.

Запуск:  python tools/inspect-exec.py 80
         python tools/inspect-exec.py 80 "Vision: проверка" "Оценка по чек-листу"
"""
import importlib.util
import json
import os
import sys

# sys.stdout здесь НЕ переопределяем: n8n-api.py уже оборачивает его в utf-8,
# а повторная обёртка закрывает тот же буфер и печать падает.
HERE = os.path.dirname(os.path.abspath(__file__))
LIMIT = 400

spec = importlib.util.spec_from_file_location("n8napi", os.path.join(HERE, "n8n-api.py"))
n8napi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n8napi)


def short(value):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= LIMIT else text[:LIMIT] + "…(+%d)" % (len(text) - LIMIT)


def walk(node, depth=0):
    pad = "  " * depth
    if isinstance(node, dict):
        for key, val in node.items():
            if isinstance(val, str) and len(val) > LIMIT:
                print("%s%s: %s" % (pad, key, short(val)))
            elif isinstance(val, (dict, list)):
                print("%s%s:" % (pad, key))
                walk(val, depth + 1)
            else:
                print("%s%s: %s" % (pad, key, short(val)))
    elif isinstance(node, list):
        for i, val in enumerate(node[:3]):
            if isinstance(val, (dict, list)):
                print("%s[%d]" % (pad, i))
                walk(val, depth + 1)
            else:
                print("%s[%d]: %s" % (pad, i, short(val)))
        if len(node) > 3:
            print("%s… ещё %d" % (pad, len(node) - 3))


def as_obj(value):
    """n8n 2.x отдаёт часть вложенных полей JSON-строками — разворачиваем их."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return None
    return value


class Deref(object):
    """n8n хранит данные «плоским» списком со ссылками-индексами в виде строк.

    Узел ссылается на свою полезную нагрузку числом в кавычках; чтобы дойти до
    вывода, ссылки нужно разворачивать по этому же списку.
    """

    def __init__(self, table):
        self.table = table

    def __call__(self, value, depth=0):
        if isinstance(value, dict) and depth < 12:
            return dict((k, self(v, depth + 1)) for k, v in value.items())
        if isinstance(value, list) and depth < 12:
            return [self(v, depth + 1) for v in value]
        if isinstance(value, str) and value.isdigit() and depth < 12:
            idx = int(value)
            if 0 <= idx < len(self.table):
                return self(self.table[idx], depth + 1)
        return value


def main():
    eid = sys.argv[1]
    want = sys.argv[2:]
    n8napi.login()
    status, body = n8napi.call("GET", "/rest/executions/%s?includeData=true" % eid)
    if status != 200:
        sys.exit("HTTP %s: %s" % (status, body[:300]))
    data = json.loads(body)["data"]
    print("Запуск %s: статус=%s, старт=%s, конец=%s" % (
        eid, data.get("status"), data.get("startedAt"), data.get("stoppedAt")))

    table = as_obj(data.get("data")) or []
    if isinstance(table, dict):
        table = [table]
    deref = Deref(table)
    result_data = deref(table[0].get("resultData")) if table else {}
    run_data = (result_data or {}).get("runData") or {}

    for name, runs in run_data.items():
        if want and name not in want:
            continue
        for run in runs:
            print("\n=== %s [%s] ===" % (name, run.get("executionStatus")))
            err = as_obj(run.get("error"))
            if err:
                print("  ОШИБКА:", short(err.get("message")))
            out = deref(run.get("data")) or {}
            for item in (out.get("main") or [[]])[0] or []:
                print("  --- вывод ---")
                walk(deref(item.get("json")), 2)
                print("  --- binary:", list((item.get("binary") or {}).keys()), "---")


if __name__ == "__main__":
    main()
