#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Живой прогресс прогона n8n: какие узлы уже отработали.

Работает только для workflow с включённым saveExecutionProgress: без него n8n
не пишет состояние узлов до самого конца выполнения, и по API видно пустой
runData — то есть непонятно, на чём прогон стоит.

Запуск:  python tools/watch-exec.py 81
         python tools/watch-exec.py 81 --every 20
"""
import argparse
import importlib.util
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

spec = importlib.util.spec_from_file_location("n8napi", os.path.join(HERE, "n8n-api.py"))
n8napi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n8napi)

FINISHED = ("success", "error", "crashed", "canceled")


def as_obj(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return None
    return value


class Deref(object):
    """n8n хранит данные «плоским» списком со ссылками-индексами в виде строк."""

    def __init__(self, table):
        self.table = table

    def __call__(self, value, depth=0):
        if isinstance(value, dict) and depth < 14:
            return dict((k, self(v, depth + 1)) for k, v in value.items())
        if isinstance(value, list) and depth < 14:
            return [self(v, depth + 1) for v in value]
        if isinstance(value, str) and value.isdigit() and depth < 14:
            idx = int(value)
            if 0 <= idx < len(self.table):
                return self(self.table[idx], depth + 1)
        return value


def fetch(eid):
    status, body = n8napi.call("GET", "/rest/executions/%s?includeData=true" % eid)
    if status != 200:
        return None, {}
    data = json.loads(body)["data"]
    table = as_obj(data.get("data")) or []
    if isinstance(table, dict):
        table = [table]
    deref = Deref(table)
    run_data = {}
    for el in table:
        if isinstance(el, dict) and "resultData" in el:
            rd = deref(el["resultData"])
            if isinstance(rd, dict) and rd.get("runData"):
                run_data = rd["runData"]
    return data, run_data


def seconds(a, b):
    fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
    try:
        return (time.mktime(time.strptime(b, fmt)) - time.mktime(time.strptime(a, fmt)))
    except (ValueError, TypeError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("execution_id")
    ap.add_argument("--every", type=int, default=20, help="период опроса, секунд")
    args = ap.parse_args()

    n8napi.login()
    seen = {}
    started = time.time()

    while True:
        data, run_data = fetch(args.execution_id)
        if data is None:
            print("не удалось прочитать запуск %s" % args.execution_id)
            return 1

        for name, runs in run_data.items():
            for i, run in enumerate(runs):
                key = (name, i)
                if key in seen:
                    continue
                st = run.get("executionStatus")
                dur = seconds(run.get("startTime"), run.get("endTime"))
                mark = "готово" if st in FINISHED else st
                line = "[%6.1f мин] %-38s %s" % ((time.time() - started) / 60.0, name, mark)
                if dur is not None:
                    line += " за %.1f с" % dur
                err = as_obj(run.get("error"))
                if err and err.get("message"):
                    line += "\n           ошибка: " + str(err["message"])[:220]
                print(line, flush=True)
                seen[key] = True

        status = data.get("status")
        if status in FINISHED:
            print("[%6.1f мин] === ЗАВЕРШЕНО: %s ===" % ((time.time() - started) / 60.0, status),
                  flush=True)
            return 0 if status == "success" else 1

        time.sleep(args.every)


if __name__ == "__main__":
    sys.exit(main())
