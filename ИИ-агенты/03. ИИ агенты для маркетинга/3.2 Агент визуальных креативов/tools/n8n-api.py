#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Работа с n8n через REST API (сервер 192.168.56.10:5678).

Использование:
    python n8n-api.py --list
    python n8n-api.py --import ../workflow-market-analyst.json
    python n8n-api.py --activate <workflowId>
    python n8n-api.py --export <workflowId> <out.json>
    python n8n-api.py --run <workflowId>
    python n8n-api.py --executions [workflowId]
"""
import argparse
import io
import json
import sys
import urllib.request
import urllib.error
import http.cookiejar

# вывод в UTF-8, иначе Windows-консоль падает на кириллице
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE = "http://192.168.56.10:5678"
EMAIL = "sokol222@list.ru"
PASSWORD = "Webnn@123"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def call(method, path, payload=None):
    url = BASE + path
    data = None
    headers = {"Accept": "application/json", "browser-id": "claude-code-setup"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with opener.open(req, timeout=120) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def login():
    st, body = call("POST", "/rest/login", {
        "emailOrLdapLoginId": EMAIL,
        "password": PASSWORD,
    })
    if st != 200:
        sys.exit("Не удалось войти в n8n: %s %s" % (st, body[:300]))
    return json.loads(body)["data"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--import", dest="import_file")
    ap.add_argument("--update", nargs=2, metavar=("ID", "FILE"))
    ap.add_argument("--activate")
    ap.add_argument("--export", nargs=2, metavar=("ID", "OUT"))
    ap.add_argument("--run")
    ap.add_argument("--executions", nargs="?", const="ALL")
    args = ap.parse_args()

    login()

    if args.list:
        st, body = call("GET", "/rest/workflows?filter=%7B%7D&skip=0&take=100")
        for w in json.loads(body).get("data", []):
            print("  %-18s active=%-5s %s" % (w.get("id"), w.get("active"), w.get("name")))

    if args.import_file:
        with open(args.import_file, encoding="utf-8") as f:
            wf = json.load(f)
        st, body = call("POST", "/rest/workflows", wf)
        print("import status:", st)
        if st in (200, 201):
            print("workflowId:", json.loads(body)["data"]["id"])
        else:
            print(body[:900])

    if args.update:
        wid, path_in = args.update
        with open(path_in, encoding="utf-8") as f:
            wf = json.load(f)
            wf.pop("id", None)
        st, body = call("PATCH", "/rest/workflows/" + wid, wf)
        print("update status:", st)
        if st not in (200, 201):
            print(body[:900])

    if args.activate:
        # В n8n активация — отдельный эндпоинт и требует текущий versionId
        wid = args.activate
        st, body = call("GET", "/rest/workflows/" + wid)
        if st != 200:
            sys.exit("не прочитать workflow: %s %s" % (st, body[:300]))
        ver = json.loads(body)["data"].get("versionId")
        st, body = call("POST", "/rest/workflows/%s/activate" % wid, {"versionId": ver})
        print("activate status:", st)
        if st in (200, 201):
            print("active:", json.loads(body)["data"].get("active"))
        else:
            print(body[:400])

    if args.export:
        wid, out = args.export
        st, body = call("GET", "/rest/workflows/" + wid)
        if st != 200:
            sys.exit("export failed: %s %s" % (st, body[:300]))
        with open(out, "w", encoding="utf-8") as f:
            json.dump(json.loads(body)["data"], f, ensure_ascii=False, indent=2)
        print("сохранено в", out)

    if args.run:
        # n8n 2.x: POST /rest/workflows/{id}/run ждёт тело {"workflowData": {...}},
        # причём id внутри тела обязан совпадать с id в URL.
        wid = args.run
        st, body = call("GET", "/rest/workflows/" + wid)
        if st != 200:
            sys.exit("не прочитать workflow: %s %s" % (st, body[:300]))
        wf = json.loads(body)["data"]
        # ... и указать, с какого триггера стартовать: без triggerToStartFrom
        # executeManually падает с "Cannot read properties of undefined".
        trig = next((n for n in wf["nodes"] if n["type"] == "n8n-nodes-base.manualTrigger"), None)
        if trig is None:
            trig = next((n for n in wf["nodes"] if n["type"].endswith("Trigger")), None)
        payload = {"workflowData": wf}
        if trig is not None:
            payload["triggerToStartFrom"] = {"name": trig["name"], "type": trig["type"]}
        st, body = call("POST", "/rest/workflows/%s/run" % wid, payload)
        print("run status:", st, body[:500])

    if args.executions:
        wid = None if args.executions == "ALL" else args.executions
        # конкатенация, а не %-форматирование: в строке есть %7B/%22, они ломают printf
        path = "/rest/executions?filter=%7B%22workflowId%22%3A%22" + (wid or "") + "%22%7D&skip=0&take=10"
        if wid is None:
            path = "/rest/executions?filter=%7B%7D&skip=0&take=10"
        st, body = call("GET", path)
        for e in json.loads(body).get("data", {}).get("results", []):
            print("  exec %-6s wf=%-18s status=%-10s started=%s" % (
                e.get("id"), e.get("workflowId"), e.get("status"), e.get("startedAt")))


if __name__ == "__main__":
    main()
