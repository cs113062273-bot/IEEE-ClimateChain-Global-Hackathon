from __future__ import annotations
import json,subprocess
from .data import ROOT,envelope

def call_bridge(payload):
    bridge=ROOT/"contracts/scripts/bridge.mjs"
    if not bridge.exists(): return {"ok":False,"status":"UNVERIFIABLE","error":{"code":"BRIDGE_UNAVAILABLE","message":"Local chain bridge is not installed"},**envelope()}
    try:
        completed=subprocess.run(["node",str(bridge)],input=json.dumps(payload),text=True,capture_output=True,timeout=90,cwd=ROOT/"contracts")
        value=json.loads(completed.stdout)
        return {**value,**envelope()}
    except (OSError,subprocess.TimeoutExpired,json.JSONDecodeError) as e:
        return {"ok":False,"status":"UNVERIFIABLE","error":{"code":"RPC_OR_BRIDGE_FAILURE","message":str(e)},**envelope()}
