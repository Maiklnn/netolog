import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
d = json.load(open("dev/exec-90.json", encoding="utf-8"))
inner = json.loads(d["data"])
print("inner keys:", list(inner.keys()))
run = inner.get("resultData", {}).get("runData", {})
print("nodes run:", len(run))
for node, runs in run.items():
    for r in runs:
        err = r.get("error")
        st = r.get("executionStatus")
        if err:
            print("ERROR node=%s" % node)
            print("  message:", str(err.get("message"))[:600])
            print("  stack:", str(err.get("stack"))[:400])
        else:
            print("ok    node=%s status=%s" % (node, st))
