import json, urllib.request, urllib.error, http.cookiejar, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BASE = "http://192.168.56.10:5678"
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def call(method, path, payload=None):
    data = None
    h = {"Accept": "application/json", "browser-id": "claude-code-setup"}
    if payload is not None:
        data = json.dumps(payload).encode(); h["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    try:
        with op.open(req, timeout=180) as r: return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e: return e.code, e.read().decode("utf-8", "replace")
call("POST", "/rest/login", {"emailOrLdapLoginId": "sokol222@list.ru", "password": "Webnn@123"})
st, body = call("GET", "/rest/executions/90?includeData=true")
d = json.loads(body)["data"]
inner = d["data"]
inner = json.loads(inner) if isinstance(inner, str) else inner
print("inner type:", type(inner).__name__, "len:", len(inner) if isinstance(inner, list) else "-")
if isinstance(inner, list):
    for i, el in enumerate(inner[:5]):
        print(" item", i, type(el).__name__, (list(el.keys())[:12] if isinstance(el, dict) else str(el)[:200]))
