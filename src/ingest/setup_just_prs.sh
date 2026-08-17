#!/usr/bin/env bash
# Installing and warming up the just-prs-mcp sidecar (polygenic risks, PGS Catalog).
# It installs uv if absent, caches the package and runs an offline self-test of the transport.
#   ./setup_just_prs.sh          # install/warm up + self-test
#   ./setup_just_prs.sh http     # the same, and start the HTTP server on :3011
set -euo pipefail
PKG="${PRS_MCP_PKG:-just-prs-mcp@0.1.3}"

if ! command -v uvx >/dev/null 2>&1; then
  echo "→ installing uv (https://docs.astral.sh/uv)…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
echo "→ uv: $(uv --version 2>/dev/null || echo '?')"

echo "→ warming up $PKG (the first time it pulls ~106 packages: pyarrow/polars/duckdb — that is normal)…"
uvx "$PKG" --help >/dev/null
echo "✓ the package is ready and cached"

echo "→ self-test of the transport (no network)…"
python3 - "$PKG" <<'PY'
import json,os,subprocess,sys
pkg=sys.argv[1]; env=dict(os.environ); env.setdefault("PRS_MCP_MODE","essentials")
p=subprocess.Popen(["uvx",pkg,"stdio"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                   stderr=subprocess.DEVNULL,env=env,text=True,bufsize=1)
def send(o): p.stdin.write(json.dumps(o)+"\n"); p.stdin.flush()
def readid(w):
    for _ in range(10000):
        l=p.stdout.readline()
        if not l: sys.exit("the server exited")
        try: m=json.loads(l)
        except ValueError: continue
        if m.get("id")==w: return m.get("result",{})
send({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"setup","version":"1"}}}); readid(1)
send({"jsonrpc":"2.0","method":"notifications/initialized"})
send({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"assess_quality","arguments":{"match_rate":0.98,"auroc":0.65,"percentile":88}}})
r=readid(2); sc=r.get("structuredContent") or {}
print("  ✓ server response:", (sc.get("quality_label") or r)); p.terminate()
PY

if [ "${1:-}" = "http" ]; then
  echo "→ starting the HTTP server on 127.0.0.1:3011 (Ctrl+C to stop)…"
  PRS_MCP_HOST=127.0.0.1 PRS_MCP_PORT=3011 exec uvx "$PKG" http
fi
echo "Done. For the application, run:  ./setup_just_prs.sh http"
