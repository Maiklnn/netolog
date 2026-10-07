# Ищет в исполнении n8n фактический ответ модели: берёт самый длинный элемент пула,
# похожий на ответ (содержит маркеры материала), и сохраняет его в файл.
#
# Запуск:  python dev/find-response.py <execId> <файл>
import json
import io
import sys
import urllib.request
import urllib.error
import http.cookiejar

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://192.168.56.10:5678"
EXEC_ID = sys.argv[1]
OUT = sys.argv[2]

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
pool = json.loads(json.loads(body)["data"]["data"])

cands = []
for i, el in enumerate(pool):
    if not isinstance(el, str):
        continue
    if "Формат ответа" in el:          # это системный промпт, а не ответ
        continue
    if "###ОСНОВНАЯ_ЧАСТЬ###" in el or "###ПОСТ_2###" in el:
        cands.append((len(el), i, el))

cands.sort(reverse=True)
if not cands:
    sys.exit("ответ модели не найден")

length, idx, text = cands[0]
print("найден ответ: элемент пула №%d, длина %d" % (idx, length))
for n, i, t in cands[1:6]:
    print("  ещё кандидат: №%d, длина %d" % (i, n))

with open(OUT, "w", encoding="utf-8") as f:
    f.write(text)
print("сохранено в", OUT)
