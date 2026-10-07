#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Диагностика: переживают ли бинарники, собранные внутри Code-узла.

Проверяем две вещи, от которых зависит запасной генератор Stable Horde:
  1. Можно ли внутри Code-узла получить настоящий Buffer по сети
     (helpers.httpRequest с encoding: null).
  2. Не портится ли картинка, если Code-узел собрал её через prepareBinaryData:
     сравниваем md5 исходного файла на сервере с тем, что записал следующий узел.

Запуск:  python tools/probe-binary-roundtrip.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SSH_KEY = "C:/Users/MIXA/.ssh/unikor"
SSH_HOST = "root@192.168.56.10"
SRC_IMAGE = "/var/lib/n8n/.n8n-files/visual-creatives/images/V1-a1.webp"
OUT_IMAGE = "/var/lib/n8n/.n8n-files/probe-out.webp"
OUT_JSON = "/var/lib/n8n/.n8n-files/probe-roundtrip.json"

spec = importlib.util.spec_from_file_location("n8napi", os.path.join(HERE, "n8n-api.py"))
n8napi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n8napi)

URL = "https://www.gstatic.com/webp/gallery/1.webp"

COPY_JS = r"""
const H = this.helpers;
const out = { tries: [] };
const URL_IMG = 'https://www.gstatic.com/webp/gallery/1.webp';

// 1. читаем байты входного бинарника и копируем их через prepareBinaryData
let buf = null;
try {
  buf = await H.getBinaryDataBuffer(0, 'data');
  out.bufLen = buf && buf.length;
} catch (e) {
  out.readError = String((e && e.message) || e);
}
if (!buf) return [{ json: Object.assign(out, { fatal: 'нет буфера' }) }];

// 2. какие способы вытащить картинку из сети дают настоящие байты
const strategies = [
  { name: 'encoding-base64', opts: { url: URL_IMG, method: 'GET', encoding: 'base64', timeout: 30000 } },
  { name: 'encoding-binary', opts: { url: URL_IMG, method: 'GET', encoding: 'binary', timeout: 30000 } },
  { name: 'encoding-null-full', opts: { url: URL_IMG, method: 'GET', encoding: null, returnFullResponse: true, timeout: 30000 } }
];

let good = null;
for (const s of strategies) {
  const rec = { name: s.name };
  try {
    const r = await H.httpRequest(s.opts);
    let body = r;
    if (s.opts.returnFullResponse) { body = r.body; rec.bodyKeys = Object.keys(r).join(','); }
    rec.kind = Object.prototype.toString.call(body);
    rec.isBuffer = Buffer.isBuffer(body);
    rec.len = body && body.length;
    let bytes = null;
    if (Buffer.isBuffer(body)) bytes = body;
    else if (typeof body === 'string') bytes = Buffer.from(body, s.name === 'encoding-base64' ? 'base64' : 'binary');
    rec.bytesLen = bytes && bytes.length;
    rec.head = bytes ? bytes.slice(0, 12).toString('hex') : null;
    if (!good && bytes && bytes.length > 1000 && rec.head && rec.head.indexOf('52494646') === 0) good = bytes;
  } catch (e) {
    rec.error = String((e && e.message) || e).slice(0, 160);
  }
  out.tries.push(rec);
}

if (!good) return [{ json: Object.assign(out, { fatal: 'ни один способ не дал валидный webp' }) }];

out.goodLen = good.length;
const bin = await H.prepareBinaryData(good, 'probe-out.webp', 'image/webp');
return [{ json: out, binary: { data: bin } }];
"""

PACK_JS = r"""
const p = $('Копировать').first().json;
const b = await helpers.prepareBinaryData(
  Buffer.from(JSON.stringify(p, null, 2), 'utf8'), 'probe-roundtrip.json', 'application/json');
return [{ json: { ok: true }, binary: { data: b } }];
"""


def code_node(name, nid, js, pos):
    return {"parameters": {"mode": "runOnceForAllItems", "jsCode": js}, "id": nid, "name": name,
            "type": "n8n-nodes-base.code", "typeVersion": 2, "position": pos}


wf = {
    "name": "PROBE binary roundtrip (удалить)",
    "nodes": [
        {"parameters": {}, "id": "e0000000-0000-4000-8000-000000000001", "name": "Manual",
         "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [0, 0]},
        {"parameters": {"operation": "read", "fileSelector": SRC_IMAGE, "options": {}},
         "id": "e0000000-0000-4000-8000-000000000002", "name": "ReadImage",
         "type": "n8n-nodes-base.readWriteFile", "typeVersion": 1, "position": [200, 0]},
        code_node("Копировать", "e0000000-0000-4000-8000-000000000003", COPY_JS, [400, 0]),
        {"parameters": {"operation": "write", "fileName": OUT_IMAGE, "dataPropertyName": "data",
                        "options": {}}, "id": "e0000000-0000-4000-8000-000000000004",
         "name": "WriteImage", "type": "n8n-nodes-base.readWriteFile", "typeVersion": 1,
         "position": [600, 0]},
        code_node("Pack", "e0000000-0000-4000-8000-000000000005", PACK_JS, [800, 0]),
        {"parameters": {"operation": "write", "fileName": OUT_JSON, "dataPropertyName": "data",
                        "options": {}}, "id": "e0000000-0000-4000-8000-000000000006",
         "name": "WriteJson", "type": "n8n-nodes-base.readWriteFile", "typeVersion": 1,
         "position": [1000, 0]},
    ],
    "connections": {
        "Manual": {"main": [[{"node": "ReadImage", "type": "main", "index": 0}]]},
        "ReadImage": {"main": [[{"node": "Копировать", "type": "main", "index": 0}]]},
        "Копировать": {"main": [[{"node": "WriteImage", "type": "main", "index": 0}]]},
        "WriteImage": {"main": [[{"node": "Pack", "type": "main", "index": 0}]]},
        "Pack": {"main": [[{"node": "WriteJson", "type": "main", "index": 0}]]},
    },
    "settings": {"executionOrder": "v1"},
}


def ssh(cmd):
    return subprocess.run(["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", SSH_HOST, cmd],
                          capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def main():
    n8napi.login()
    ssh("rm -f %s %s" % (OUT_IMAGE, OUT_JSON))
    st, body = n8napi.call("POST", "/rest/workflows", wf)
    if st not in (200, 201):
        sys.exit("import failed: %s %s" % (st, body[:500]))
    wid = json.loads(body)["data"]["id"]
    print("workflowId:", wid)

    st, body = n8napi.call("GET", "/rest/workflows/" + wid)
    wf_data = json.loads(body)["data"]
    st, body = n8napi.call("POST", "/rest/workflows/%s/run" % wid, {
        "workflowData": wf_data,
        "triggerToStartFrom": {"name": "Manual", "type": "n8n-nodes-base.manualTrigger"},
    })
    print("run:", st, body[:200])

    res = ""
    for _ in range(30):
        time.sleep(4)
        res = ssh("cat %s 2>/dev/null" % OUT_JSON)
        if res.strip():
            break
    print("=== PROBE RESULT ===")
    print(res)
    print("=== MD5 ===")
    print(ssh("md5sum %s %s 2>/dev/null; ls -la %s %s 2>/dev/null" % (SRC_IMAGE, OUT_IMAGE, SRC_IMAGE, OUT_IMAGE)))
    n8napi.call("DELETE", "/rest/workflows/" + wid)
    ssh("rm -f %s %s" % (OUT_IMAGE, OUT_JSON))


if __name__ == "__main__":
    main()
