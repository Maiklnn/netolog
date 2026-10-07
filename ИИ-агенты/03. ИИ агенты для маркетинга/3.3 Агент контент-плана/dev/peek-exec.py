# Разбор исполнения n8n: n8n хранит данные в «плоском» пуле, где строки-числа —
# ссылки на элементы. Скрипт разыменовывает их и печатает ошибку и упавший узел.
import json
import io
import sys
import urllib.request
import urllib.error
import http.cookiejar

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://192.168.56.10:5678"
EXEC_ID = sys.argv[1] if len(sys.argv) > 1 else "90"

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def call(method, path, payload=None):
    data = None
    headers = {"Accept": "application/json", "browser-id": "claude-code-setup"}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with op.open(req, timeout=180) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


call("POST", "/rest/login", {"emailOrLdapLoginId": "sokol222@list.ru", "password": "Webnn@123"})
st, body = call("GET", "/rest/executions/%s?includeData=true" % EXEC_ID)
inner = json.loads(json.loads(body)["data"]["data"])


def deref(v):
    if isinstance(v, str):
        try:
            i = int(v)
        except ValueError:
            return v
        if 0 <= i < len(inner):
            return inner[i]
    return v


for el in inner:
    if isinstance(el, dict) and "error" in el:
        print("УПАВШИЙ УЗЕЛ:", deref(el.get("lastNodeExecuted")))
        err = deref(el["error"])
        if isinstance(err, dict):
            for k, v in err.items():
                print("  %s: %s" % (k, str(deref(v))[:800]))
        else:
            print("ОШИБКА:", str(err)[:1500])
        rd = deref(el.get("runData"))
        if isinstance(rd, list):
            print("--- узлы ---")
            for it in rd:
                if not isinstance(it, dict):
                    continue
                print("  узел:", deref(it.get("node")), "| статус:", deref(it.get("executionStatus")))
                if "error" in it:
                    e = deref(it["error"])
                    print("     err:", json.dumps(e, ensure_ascii=False)[:900] if not isinstance(e, str) else e[:900])
        break
