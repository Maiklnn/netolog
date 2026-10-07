#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Диагностика: как в этом n8n лежат бинарные данные внутри Code-узла.

Создаёт временный workflow (Manual -> чтение картинки -> Probe -> запись JSON),
запускает его и читает результат с диска сервера по SSH.

Запуск:  python tools/probe-binary.py
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
OUT_ON_SERVER = "/var/lib/n8n/.n8n-files/binary-probe.json"

spec = importlib.util.spec_from_file_location("n8napi", os.path.join(HERE, "n8n-api.py"))
n8napi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n8napi)

PROBE_JS = r"""
const H = this.helpers;
const out = { helperKeys: Object.keys(H || {}) };
try {
  const item = $input.first();
  const j = item.json;
  out.jsonKeys = Object.keys(j);
  out.binKeys = item.binary ? Object.keys(item.binary) : null;
  const bin = item.binary && item.binary.data ? item.binary.data : null;
  if (bin) {
    out.binMetaKeys = Object.keys(bin);
    out.dataType = typeof bin.data;
    out.dataHead = String(bin.data).slice(0, 60);
    out.dataLen = String(bin.data).length;
    out.looksLikeBase64 = /^[A-Za-z0-9+/=]+$/.test(String(bin.data));
  }
  out.hasGetBuffer = typeof H.getBinaryDataBuffer;
  try {
    const buf = await H.getBinaryDataBuffer(0, 'data');
    out.bufCtor = buf && buf.constructor ? buf.constructor.name : typeof buf;
    out.bufIsBuffer = Buffer.isBuffer(buf);
    out.bufLen = buf && buf.length;
    out.bufB64Head = (Buffer.isBuffer(buf) ? buf.toString('base64') : String(buf)).slice(0, 40);
  } catch (e) {
    out.bufError = String((e && e.message) || e);
  }
} catch (e) {
  out.fatal = String((e && e.stack) || e);
}
return [{ json: out }];
"""

PACK_JS = r"""
const p = $('Probe').first().json;
const bin = await helpers.prepareBinaryData(
  Buffer.from(JSON.stringify(p, null, 2), 'utf8'), 'binary-probe.json', 'application/json');
return [{ json: { ok: true }, binary: { data: bin } }];
"""


def code_node(name, nid, js, pos):
    return {"parameters": {"mode": "runOnceForAllItems", "jsCode": js}, "id": nid, "name": name,
            "type": "n8n-nodes-base.code", "typeVersion": 2, "position": pos}


wf = {
    "name": "PROBE binary (удалить)",
    "nodes": [
        {"parameters": {}, "id": "d0000000-0000-4000-8000-000000000001", "name": "Manual",
         "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [0, 0]},
        {"parameters": {"operation": "read", "fileSelector": SRC_IMAGE, "options": {}},
         "id": "d0000000-0000-4000-8000-000000000002", "name": "ReadImage",
         "type": "n8n-nodes-base.readWriteFile", "typeVersion": 1, "position": [200, 0]},
        code_node("Probe", "d0000000-0000-4000-8000-000000000003", PROBE_JS, [400, 0]),
        code_node("Pack", "d0000000-0000-4000-8000-000000000004", PACK_JS, [600, 0]),
        {"parameters": {"operation": "write", "fileName": OUT_ON_SERVER,
                        "dataPropertyName": "data", "options": {}},
         "id": "d0000000-0000-4000-8000-000000000005", "name": "WriteProbe",
         "type": "n8n-nodes-base.readWriteFile", "typeVersion": 1, "position": [800, 0]},
    ],
    "connections": {
        "Manual": {"main": [[{"node": "ReadImage", "type": "main", "index": 0}]]},
        "ReadImage": {"main": [[{"node": "Probe", "type": "main", "index": 0}]]},
        "Probe": {"main": [[{"node": "Pack", "type": "main", "index": 0}]]},
        "Pack": {"main": [[{"node": "WriteProbe", "type": "main", "index": 0}]]},
    },
    "settings": {"executionOrder": "v1"},
}


def ssh(cmd):
    return subprocess.run(["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", SSH_HOST, cmd],
                          capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def main():
    n8napi.login()
    ssh("rm -f " + OUT_ON_SERVER)
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
        res = ssh("cat %s 2>/dev/null" % OUT_ON_SERVER)
        if res.strip():
            break
    print("=== PROBE RESULT ===")
    print(res)
    n8napi.call("DELETE", "/rest/workflows/" + wid)
    ssh("rm -f " + OUT_ON_SERVER)


if __name__ == "__main__":
    main()
