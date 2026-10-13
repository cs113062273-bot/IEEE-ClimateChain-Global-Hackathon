"""Independent stdlib-only verifier: SHA, physical constraints, jobs and metrics.
Imports no backend implementation. Integrity is not physical meter truth.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
from decimal import Decimal,ROUND_HALF_EVEN,DecimalException
from datetime import datetime,timedelta

def canonical(value):
    def convert(v):
        if v is None or isinstance(v,(bool,str)):return v
        if isinstance(v,int):
            if abs(v)>9007199254740991:raise ValueError("unsafe integer")
            return v
        if isinstance(v,float):
            if not math.isfinite(v):raise ValueError("nonfinite number")
            try:d=Decimal(str(v)).quantize(Decimal("0.000000001"),rounding=ROUND_HALF_EVEN)
            except DecimalException as exc:raise ValueError("Canonical float magnitude exceeds supported decimal precision") from exc
            return format(abs(d) if d==0 else d,".9f")
        if isinstance(v,list):return [convert(i) for i in v]
        if isinstance(v,dict):
            if any(not isinstance(k,str) or not k.isascii() for k in v):raise ValueError("non-ASCII key")
            return {k:convert(v[k]) for k in sorted(v)}
        raise ValueError("unsupported type")
    return json.dumps(convert(value),ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")

def sha(value):return hashlib.sha256(canonical(value)).hexdigest()

def inspect(evidence,expected,root):
    errors=[];warnings=[];actual=sha(evidence);tol=2e-5
    if actual!=expected.removeprefix("0x"):errors.append("SHA256 mismatch")
    if evidence.get("schema_version")!="1.0.0" or evidence.get("canonicalization")!="gridproof-canonical-json-v1/float-decimal-strings-9":errors.append("unsupported schema")
    if evidence.get("methodology")!="gridproof/location-based-operational-scenario/v1":errors.append("unsupported methodology")
    if evidence.get("observational_status")!="simulation_using_public_grid_data":errors.append("unsupported observational status")
    if evidence.get("claim_scope",{}).get("category")!="modelled-grid-emissions-exposure":errors.append("unsupported claim category")
    try:
        data=evidence["inputs"];s=data["scenario"];n=lambda obj,k:float(obj[k])
        if sha(data)!=evidence["input_sha256"]:errors.append("input digest mismatch")
        if len(data["intervals"])!=48:errors.append("not 48 intervals")
        energies={};costs={}
        for key,starts_key in [("dispatch","batch_starts"),("baseline_dispatch","baseline_batch_starts")]:
            records=data[key];starts=data[starts_key]
            if len(records)!=48:errors.append("invalid dispatch length");continue
            for t,x in enumerate(records):
                src=data["intervals"][t]
                energy_fields=["grid_import_kwh","battery_charge_kwh","battery_discharge_kwh","soc_start_kwh","soc_end_kwh","ev_charge_kwh","batch_load_kwh","pv_used_kwh","pv_curtail_kwh","export_kwh"]
                if any(not math.isfinite(n(x,f)) or n(x,f)<-tol for f in energy_fields):errors.append("negative/nonfinite energy")
                for field,maximum in [("ci_actual_g_per_kwh",1500),("ci_forecast_g_per_kwh",1500),("tariff_gbp_per_kwh",10),("fixed_load_kwh",200),("pv_available_kwh",200)]:
                    if not math.isfinite(n(x,field)) or not 0<=n(x,field)<=maximum:errors.append("invalid input "+field)
                if len(x["ev_by_job_kwh"])!=len(s["ev_jobs"]) or any(not math.isfinite(float(v)) or float(v)<-tol for v in x["ev_by_job_kwh"]):errors.append("invalid per-job EV energy")
                if n(x,"export_kwh")>tol:errors.append("export forbidden")
                if n(x,"pv_used_kwh")>n(x,"pv_available_kwh")+tol:errors.append("PV used exceeds available")
                for field in ["start_utc","end_utc","fixed_load_kwh","pv_available_kwh","ci_actual_g_per_kwh","ci_forecast_g_per_kwh","tariff_gbp_per_kwh"]:
                    if src[field]!=x[field]:errors.append(f"input mismatch {key} {t} {field}")
                start=datetime.fromisoformat(x["start_utc"].replace("Z","+00:00"));end=datetime.fromisoformat(x["end_utc"].replace("Z","+00:00"))
                if end-start!=timedelta(minutes=30) or start.utcoffset()!=timedelta(0) or end.utcoffset()!=timedelta(0):errors.append("invalid UTC slot")
                if t and records[t-1]["end_utc"]!=x["start_utc"]:errors.append("nonconsecutive UTC slot")
                balance=n(x,"grid_import_kwh")+n(x,"battery_discharge_kwh")+n(x,"pv_used_kwh")-n(x,"fixed_load_kwh")-n(x,"ev_charge_kwh")-n(x,"batch_load_kwh")-n(x,"battery_charge_kwh")
                if abs(balance)>tol:errors.append(f"energy conservation {key} {t}")
                soc=n(x,"soc_start_kwh")+n(s,"eta_charge")*n(x,"battery_charge_kwh")-n(x,"battery_discharge_kwh")/n(s,"eta_discharge")
                if abs(soc-n(x,"soc_end_kwh"))>tol:errors.append(f"SoC dynamics {key} {t}")
                cap=n(s,"battery_capacity_kwh")
                if not cap*n(s,"soc_min_fraction")-tol<=n(x,"soc_start_kwh")<=cap*n(s,"soc_max_fraction")+tol:errors.append("SoC start bound")
                if not cap*n(s,"soc_min_fraction")-tol<=n(x,"soc_end_kwh")<=cap*n(s,"soc_max_fraction")+tol:errors.append("SoC bound")
                if t and abs(n(records[t-1],"soc_end_kwh")-n(x,"soc_start_kwh"))>tol:errors.append("SoC continuity")
                if min(n(x,"battery_charge_kwh"),n(x,"battery_discharge_kwh"))>tol:errors.append("simultaneous battery modes")
                for energy,power in [("grid_import_kwh","max_grid_import_kw"),("battery_charge_kwh","charge_kw"),("battery_discharge_kwh","discharge_kw"),("ev_charge_kwh","charger_station_kw")]:
                    if not -tol<=n(x,energy)<=n(s,power)*.5+tol:errors.append("power cap "+energy)
                if abs(n(x,"pv_used_kwh")+n(x,"pv_curtail_kwh")-n(x,"pv_available_kwh"))>tol:errors.append("PV allocation")
                if abs(sum(float(v) for v in x["ev_by_job_kwh"])-n(x,"ev_charge_kwh"))>tol:errors.append("EV aggregate")
            initial=n(s,"battery_capacity_kwh")*n(s,"soc_initial_fraction")
            if abs(n(records[0],"soc_start_kwh")-initial)>tol or abs(n(records[-1],"soc_end_kwh")-initial)>tol:errors.append("initial/terminal SoC")
            for j,job in enumerate(s["ev_jobs"]):
                values=[float(x["ev_by_job_kwh"][j]) for x in records]
                if abs(sum(values)-n(job,"energy_kwh"))>tol:errors.append("EV energy")
                for t,v in enumerate(values):
                    if v< -tol or v>n(job,"max_kw")*.5+tol or (not job["arrival_slot"]<=t<job["deadline_slot"] and v>tol):errors.append("EV window/cap")
            batch=[0.0]*48;occupancy=[0]*48
            for job in s["batch_jobs"]:
                start=starts[job["id"]]
                if not job["earliest_start_slot"]<=start<=job["latest_end_slot"]-job["duration_slots"]:errors.append("batch start")
                for t in range(start,start+job["duration_slots"]):batch[t]+=n(job,"energy_kwh")/job["duration_slots"];occupancy[t]+=1
            for t,x in enumerate(records):
                if abs(batch[t]-n(x,"batch_load_kwh"))>tol or occupancy[t]>s["max_batch_concurrency"]:errors.append("batch duration/concurrency")
            energies[key]=sum(n(x,"grid_import_kwh")*n(x,"ci_actual_g_per_kwh") for x in records)/1000
            costs[key]=sum(n(x,"grid_import_kwh")*n(x,"tariff_gbp_per_kwh") for x in records)
        results=evidence["results"]
        for name,value in {"baseline_kgco2":energies["baseline_dispatch"],"plan_kgco2":energies["dispatch"],"difference_kgco2":energies["baseline_dispatch"]-energies["dispatch"],"cost_gbp":costs["dispatch"],"baseline_cost_gbp":costs["baseline_dispatch"]}.items():
            claimed=float(results[name])
            if not math.isfinite(claimed) or not math.isfinite(value) or abs(value-claimed)>tol:errors.append("metric mismatch "+name)
        scope=evidence["claim_scope"]
        if scope["site_hash"]!=s["site_id_hash"] or scope["from_utc"]!=data["intervals"][0]["start_utc"] or scope["to_utc"]!=data["intervals"][-1]["end_utc"]:errors.append("claim scope mismatch")
        for source in evidence["source_snapshots"]+evidence["reproduction"]["artifact_hashes"]:
            path=(root/source["path"]).resolve()
            if root.resolve() not in path.parents:errors.append("source path outside root");continue
            if not path.exists():warnings.append("source unavailable: "+source["path"]);continue
            if hashlib.sha256(path.read_bytes()).hexdigest()!=source["sha256"]:errors.append("source digest mismatch: "+source["path"])
    except (KeyError,ValueError,TypeError,IndexError) as exc:errors.append("invalid content: "+str(exc))
    return {"verified":not errors,"status":"VERIFIED" if not errors else "INVALID","sha256":actual,"errors":sorted(set(errors)),"warnings":warnings,"trust_boundary":"Integrity, inputs, physical constraints and modeled arithmetic; not meter truth or real avoided emissions"}

def main():
    parser=argparse.ArgumentParser();parser.add_argument("path");parser.add_argument("--digest");parser.add_argument("--root",default=str(Path(__file__).resolve().parents[1]));args=parser.parse_args()
    payload=json.loads(Path(args.path).read_text(encoding="utf-8-sig"));evidence=payload.get("evidence",payload)
    expected=args.digest or payload.get("digest") or payload.get("sha256")
    if not expected:raise SystemExit("--digest required for raw evidence")
    result=inspect(evidence,expected,Path(args.root));print(json.dumps(result,indent=2));raise SystemExit(0 if result["verified"] else 1)
if __name__=="__main__":main()
