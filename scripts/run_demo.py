"""Launch local API, dashboard and zero-cost chain; never autoattest or publish."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"

def port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1): return True
    except OSError: return False

def wait_ready(url, process, label, limit=60):
    end = time.monotonic()+limit
    while time.monotonic()<end:
        if process is not None and process.poll() is not None:
            raise RuntimeError(f"{label} exited ({process.returncode}). Read .runtime/{label}.log")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status==200: return
        except (OSError, TimeoutError): pass
        time.sleep(.5)
    raise RuntimeError(f"{label} did not become ready: {url}. Read .runtime/{label}.log")

def main():
    if sys.version_info[:2] != (3,11):
        raise RuntimeError("Use Python 3.11 from the project virtual environment.")
    node=shutil.which("node")
    if not node: raise RuntimeError("Node 24 is required. Run scripts/setup first.")
    RUNTIME.mkdir(exist_ok=True)
    owned=[]; handles=[]
    def start(label,args,cwd=ROOT):
        log=(RUNTIME/f"{label}.log").open("a",encoding="utf-8")
        handles.append(log)
        process=subprocess.Popen(args,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        owned.append(process)
        return process
    try:
        subprocess.run([node,str(ROOT/"contracts/scripts/start-local.mjs")],cwd=ROOT/"contracts",check=True)
        if port_open(8000):
            with urllib.request.urlopen("http://127.0.0.1:8000/api/health",timeout=3) as response:
                if json.load(response).get("service")!="GridProof": raise RuntimeError("Port 8000 belongs to another service.")
        else:
            process=start("api",[sys.executable,"-m","uvicorn","backend.app.main:app","--host","127.0.0.1","--port","8000"])
            wait_ready("http://127.0.0.1:8000/api/health",process,"api")
        with urllib.request.urlopen("http://127.0.0.1:8000/api/health",timeout=3) as response:
            if json.load(response).get("fixture_status")!="ready": raise RuntimeError("Offline fixture is missing or incomplete.")
        if port_open(3000):
            with urllib.request.urlopen("http://127.0.0.1:3000",timeout=5) as response:
                if b"GridProof" not in response.read(): raise RuntimeError("Port 3000 belongs to another application.")
        else:
            mode="start" if (ROOT/"frontend/.next/BUILD_ID").exists() else "dev"
            process=start("web",[node,str(ROOT/"frontend/node_modules/next/dist/bin/next"),mode,"--hostname","127.0.0.1","--port","3000"],ROOT/"frontend")
            wait_ready("http://127.0.0.1:3000",process,"web")
        print("GridProof ready: http://127.0.0.1:3000",flush=True)
        print("API documentation: http://127.0.0.1:8000/docs",flush=True)
        print("Local EVM: 127.0.0.1:8545 / chain 31337. No evidence autoattested.",flush=True)
        print("Press Ctrl+C to stop API/dashboard processes started by this command.",flush=True)
        while True:
            for process in owned:
                if process.poll() is not None: raise RuntimeError("A demo service stopped. Inspect .runtime logs.")
            time.sleep(1)
    except KeyboardInterrupt: pass
    finally:
        for process in reversed(owned):
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill()
        for handle in handles: handle.close()

if __name__=="__main__": main()
