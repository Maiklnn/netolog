#!/usr/bin/env python3
"""Извлекаем данные последнего выполнения workflow из БД n8n"""
import sqlite3, json, sys

DB = "/home/vagrant/.n8n/database.sqlite"
conn = sqlite3.connect(DB)
cur = conn.cursor()

# Берём последнюю завершённую execution
cur.execute("SELECT executionId, data FROM execution_data ORDER BY executionId DESC LIMIT 1")
row = cur.fetchone()
if not row:
    print("Нет завершённых выполнений")
    sys.exit(1)

exec_id, raw = row
print(f"Execution ID: {exec_id}")

data = json.loads(raw)
if isinstance(data, str):
    data = json.loads(data)

def find_rd(obj, depth=0):
    if depth > 5: return None
    if isinstance(obj, dict):
        if "resultData" in obj: return obj["resultData"]
        for v in obj.values():
            r = find_rd(v, depth+1)
            if r: return r
    elif isinstance(obj, list):
        for item in obj:
            r = find_rd(item, depth+1)
            if r: return r
    return None

rd = find_rd(data)
print(f"rd type after find: {type(rd)}")
if isinstance(rd, str):
    print(f"rd first 200 chars: {rd[:200]}")
    rd = json.loads(rd)
    print(f"rd type after json.loads: {type(rd)}")
if isinstance(rd, str):
    rd = json.loads(rd)
    print(f"rd type after 2nd json.loads: {type(rd)}")
if not rd or isinstance(rd, str):
    print(f"FAILED. data type: {type(data)}")
    print(json.dumps(data, ensure_ascii=False)[:3000])
    sys.exit(1)

run_data = rd.get("runData", {})

for node_name, runs in run_data.items():
    print(f"\n=== {node_name} ===")
    for run in runs:
        main = run.get("data", {}).get("main", [])
        if main and main[0]:
            for item in main[0]:
                j = item.get("json", {})
                # Для узла Calendar — показываем полный ответ
                if "Calendar" in node_name or "calendar" in node_name.lower():
                    print(json.dumps(j, ensure_ascii=False, indent=2)[:2000])
                else:
                    # Для остальных — кратко
                    keys = list(j.keys())
                    print(f"  keys: {keys}")
                    # Показываем caldav_url и ical_body для Parse and Build
                    if "caldav_url" in j:
                        print(f"  caldav_url: {j['caldav_url']}")
                        print(f"  ical_body (first 300): {repr(j.get('ical_body','')[:300])}")
                    if "requestBody" in j:
                        print(f"  model: {j['requestBody'].get('model')}")
                        print(f"  message: {j['requestBody'].get('messages',[{}])[1].get('content','')[:100]}")

conn.close()