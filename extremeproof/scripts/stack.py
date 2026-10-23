"""Start the whole local demo: chain, contracts, two providers, hub (and the web app).

    extremeproof/.venv/Scripts/python -m extremeproof.scripts.stack            # everything
    extremeproof/.venv/Scripts/python -m extremeproof.scripts.stack --no-web   # services only

The chain clock starts on a simulated date (default 2021-05-01) so past
summers (2021-2026) can be replayed with "lock before the season starts" enforced by the
contract. Nothing leaves this machine; no accounts or API keys are needed.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
NPX = "npx.cmd" if os.name == "nt" else "npx"
NPM = "npm.cmd" if os.name == "nt" else "npm"


def wait_http(url, body=None, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3):
                return True
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"{url} did not come up")


class Stack:
    def __init__(self, chain_start="2021-05-01T00:00:00Z", chain_port=8545, hub_port=8600,
                 provider_ports=(8601, 8602), web_port=3000, web=True, runtime=None, log_dir=None):
        self.chain_start, self.chain_port, self.hub_port = chain_start, chain_port, hub_port
        self.provider_ports, self.web_port, self.web = provider_ports, web_port, web
        self.runtime = Path(runtime or ROOT / ".runtime")
        self.log_dir = Path(log_dir or self.runtime / "logs")
        self.procs = []
        self.rpc = f"http://127.0.0.1:{chain_port}"

    def spawn(self, name, args, cwd, env=None):
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log = open(self.log_dir / f"{name}.log", "w", encoding="utf-8")
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        p = subprocess.Popen(args, cwd=cwd, env={**os.environ, **(env or {})}, stdout=log, stderr=subprocess.STDOUT,
                             creationflags=flags)
        self.procs.append((name, p))
        return p

    def start(self):
        self.runtime.mkdir(parents=True, exist_ok=True)
        deployment = self.runtime / "deployment.json"
        for stale in (deployment, self.runtime / "chain-snapshot.json"):
            if stale.exists():
                stale.unlink()
        for d in ("providers", "specs"):
            for f in (self.runtime / d).rglob("*.json") if (self.runtime / d).exists() else []:
                f.unlink()
        contracts = ROOT / "contracts"
        self.spawn("chain", [NPX, "hardhat", "node", "--network", "hardhatMainnet", "--hostname", "127.0.0.1",
                             "--port", str(self.chain_port)], contracts, {"EXTREMEPROOF_CHAIN_START": self.chain_start})
        wait_http(self.rpc, json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []}).encode())
        env = {"EP_RPC": self.rpc}
        dep_env = {**env, "EP_DEPLOYMENT": str(deployment)}
        out = subprocess.run(["node", "scripts/deploy.mjs"], cwd=contracts, env={**os.environ, **dep_env},
                             capture_output=True, text=True)
        if out.returncode != 0:
            raise RuntimeError(out.stderr or out.stdout)
        print(out.stdout.strip())
        dep = json.loads(deployment.read_text(encoding="utf-8"))
        py = sys.executable
        for (source, key), port in zip((("station", dep["demoKeys"]["providerStation"]),
                                        ("era5", dep["demoKeys"]["providerEra5"])), self.provider_ports):
            self.spawn(f"provider-{source}", [py, "-m", "uvicorn", "extremeproof.providers.service:app", "--host", "127.0.0.1",
                                              "--port", str(port)], REPO,
                       {**dep_env, "EP_PROVIDER_SOURCE": source, "EP_PROVIDER_KEY": key, "EP_DEMO_ATTACKS": "1",
                        "EP_STATE_DIR": str(self.runtime / "providers" / source)})
        providers = ",".join(f"http://127.0.0.1:{p}" for p in self.provider_ports)
        self.spawn("hub", [py, "-m", "uvicorn", "extremeproof.server.hub:app", "--host", "127.0.0.1", "--port", str(self.hub_port)],
                   REPO, {**dep_env, "EP_PROVIDERS": providers})
        for port in self.provider_ports:
            wait_http(f"http://127.0.0.1:{port}/health")
        wait_http(f"http://127.0.0.1:{self.hub_port}/api/health")
        if self.web:
            web = ROOT / "web"
            self.spawn("web", [NPM, "run", "start", "--", "--port", str(self.web_port)], web,
                       {"NEXT_PUBLIC_EP_HUB": f"http://127.0.0.1:{self.hub_port}", "NEXT_PUBLIC_EP_RPC": self.rpc})
            wait_http(f"http://127.0.0.1:{self.web_port}/", timeout=120)
        return dep

    def stop(self):
        for name, p in reversed(self.procs):
            if p.poll() is None:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
                else:
                    p.send_signal(signal.SIGTERM)
        for _, p in self.procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
        self.procs.clear()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chain-start", default="2021-05-01T00:00:00Z")
    ap.add_argument("--no-web", action="store_true")
    a = ap.parse_args()
    s = Stack(chain_start=a.chain_start, web=not a.no_web)
    try:
        s.start()
        print(f"chain  {s.rpc} (clock starts {a.chain_start}, simulated)")
        print(f"hub    http://127.0.0.1:{s.hub_port}")
        print(f"providers {', '.join(f'http://127.0.0.1:{p}' for p in s.provider_ports)}")
        if s.web:
            print(f"web    http://127.0.0.1:{s.web_port}")
        print("logs in", s.log_dir, "- press Ctrl+C to stop")
        while all(p.poll() is None for _, p in s.procs):
            time.sleep(1)
        print("a service stopped; see logs")
    except KeyboardInterrupt:
        pass
    finally:
        s.stop()


if __name__ == "__main__":
    main()
