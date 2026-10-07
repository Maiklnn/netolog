import json, sys, subprocess

sys.path.insert(0, 'tools')
exec(open('tools/n8n-api.py', encoding='utf-8').read().split('def main()')[0])

import urllib.request, urllib.parse, http.cookiejar
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
BASE = 'http://192.168.56.10:5678'
req = urllib.request.Request(BASE + '/rest/login', data=json.dumps({'emailOrLdapLoginId': 'admin@example.com', 'password': 'Webnn@123'}).encode(), headers={'Content-Type': 'application/json'})
op.open(req)

def get(u):
    return json.loads(op.open(BASE + u).read().decode())

ex = get('/rest/executions?limit=1&filter=' + urllib.parse.quote(json.dumps({'workflowId': 'aVbrHDT74iC2tRQ1'})))
eid = ex['data']['results'][0]['id']
raw = get('/rest/executions/%d?includeData=true' % eid)

data = raw['data']
if isinstance(data, str):
    data = json.loads(data)
if isinstance(data, list):
    data = data[data.index('resultData') + 1] if 'resultData' in data else data

def deref(v, pool, seen=None):
    if isinstance(v, str):
        if v.isdigit() and int(v) < len(pool):
            return deref(pool[int(v)], pool)
        return v
    if isinstance(v, list):
        return [deref(x, pool) for x in v]
    if isinstance(v, dict):
        return {k: deref(x, pool) for k, x in v.items()}
    return v

rd = deref(data, data) if isinstance(data, list) else data
run = rd.get('resultData', {}).get('runData', {})
print('exec', eid, '| статус:', raw['data'] if not isinstance(raw['data'], (list, dict)) else raw.get('status'))
for name, runs in run.items():
    if len(runs) > 1 or 'LLM' in name:
        print('  %-45s выполнений: %d' % (name, len(runs)))
