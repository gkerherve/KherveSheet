import json, subprocess, sys, os
KS = os.path.expanduser("~/Documents/PycharmProjects/KherveSheet")
class MCP:
    def __init__(self, log="calls.jsonl"):
        self.p = subprocess.Popen([KS+"/.venv/bin/python","-m","khervesheet.mcp_server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, env={**os.environ,"PYTHONPATH":KS})
        self.i = 0; self.log = open(log,"a")
        self.rpc("initialize", {"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"joss-demo","version":"1"}})
    def rpc(self, method, params=None):
        self.i += 1
        self.p.stdin.write((json.dumps({"jsonrpc":"2.0","id":self.i,"method":method,"params":params or {}})+"\n").encode()); self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())
    def call(self, _tool, **args):
        r = self.rpc("tools/call", {"name":_tool,"arguments":args})
        self.log.write(json.dumps({"tool":_tool,"arguments":args})+"\n"); self.log.flush()
        res = r.get("result", r)
        txt = res["content"][0]["text"] if "content" in res else json.dumps(res)
        if res.get("isError"): print("ERROR", _tool, txt[:500], file=sys.stderr)
        return txt
