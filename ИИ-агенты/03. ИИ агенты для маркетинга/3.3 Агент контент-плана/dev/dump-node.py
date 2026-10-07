# Достаёт вывод конкретного узла из исполнения n8n.
# Данные исполнения хранятся «плоско»: строки-числа — ссылки на элементы пула,
# поэтому значения разыменовываются рекурсивно.
#
# Запуск:  python dev/dump-node.py <execId> "<имя узла>" [файл]
import json
import io
import os
import sys
import urllib.request
import urllib.error
import http.cookiejar

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://192.168.56.10:5678"
EXEC_ID = sys.argv[1]
NODE = sys.argv[2]
OUT = sys.argv[3] if len(sys.argv) > 3 else None

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
if st != 200:
    sys.exit("не прочитать исполнение: %s %s" % (st, body[:300]))

pool = json.loads(json.loads(body)["data"]["data"])
LIMIT = len(pool)


def deref(v, depth=0):
    if depth > 8:
        return v
    if isinstance(v, str):
        if v.isdigit() and len(v) <= 6:
            i = int(v)
            if 0 <= i < LIMIT:
                return deref(pool[i], depth + 1)
        return v
    return v


def find_run_data():
    for el in pool:
        if isinstance(el, dict) and "runData" in el:
            rd = deref(el["runData"], 1)
            if isinstance(rd, dict) and rd:
                return rd
    return {}


rd = find_run_data()
print("узлы в исполнении:", ", ".join(list(rd.keys())))

runs = rd.get(NODE)
if not runs:
    sys.exit("узел не найден: " + NODE)

r = deref(runs[0], 1)
data = deref(r.get("data"), 1)
text = None
try:
    items = data["main"][0]
    text = deref(items[0]["json"], 1).get("text")
except Exception as e:  # noqa: BLE001
    print("не удалось достать text:", e)

if text is None:
    # фолбэк: ищем ответ модели прямо в сериализованном исполнении
    # в исполнении есть и промпт, и ответ — берём последнее вхождение маркера
    blob = json.dumps(pool, ensure_ascii=False)
    i = blob.rfind("###ПОСТ_1###")
    if i < 0:
        i = blob.rfind("###РИЛС###")
    if i < 0:
        sys.exit("ответ модели не найден в исполнении")
    start = max(0, i - 300)
    text = blob[start:i + 9000]
    print("!!! поле text не найдено, показан фрагмент сериализованного исполнения")
    if OUT:
        with open(OUT, "w", encoding="utf-8") as f:
            f.write(text)
        print("сохранено в", OUT)
    else:
        print(text)
    sys.exit(0)

print("длина ответа:", len(text))
if OUT:
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print("сохранено в", OUT)
else:
    print(text[:3000])
