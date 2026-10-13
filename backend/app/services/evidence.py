"""Explicit, tested canonical encoding; numeric floats are decimal strings.

This is gridproof-canonical-json-v1, deliberately NOT an RFC8785 claim.
All object keys ASCII, sorted; UTF-8 compact JSON; finite floats become fixed
9-place decimal strings; integers limited to JavaScript's exact safe range.
"""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_EVEN, DecimalException
import hashlib,json,math,subprocess
from pathlib import Path
from backend.app.domain.schemas import Scenario
from backend.app.domain.solver import check_constraints
from .data import ROOT, envelope, sources
from .storage import get,put

def normalize(value):
    if isinstance(value,bool) or value is None or isinstance(value,str): return value
    if isinstance(value,int):
        if abs(value)>9007199254740991: raise ValueError("Canonical integer exceeds JS safe range")
        return value
    if isinstance(value,float):
        if not math.isfinite(value): raise ValueError("Nonfinite evidence number")
        try: val=Decimal(str(value)).quantize(Decimal("0.000000001"),rounding=ROUND_HALF_EVEN)
        except DecimalException as exc: raise ValueError("Canonical float magnitude exceeds supported decimal precision") from exc
        return format(abs(val) if val==0 else val,".9f")
    if isinstance(value,list): return [normalize(x) for x in value]
    if isinstance(value,dict):
        if any(not isinstance(k,str) or not k.isascii() for k in value): raise ValueError("Canonical keys must be ASCII strings")
        return {k:normalize(value[k]) for k in sorted(value)}
    raise ValueError(f"Unsupported evidence value type {type(value).__name__}")

def canonical_bytes(value):
    return json.dumps(normalize(value),ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")

def digest(value): return hashlib.sha256(canonical_bytes(value)).hexdigest()

def file_hash(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def make_evidence(run_id,policy="hybrid"):
    run=get(run_id,"run"); plan=run["plans"][policy]; baseline=run["plans"]["immediate"]
    if not plan["constraints"]["verified"] or not baseline["constraints"]["verified"]: raise ValueError("Evidence requires verified feasible baseline and plan")
    try: commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
    except (OSError,subprocess.CalledProcessError): commit="uncommitted-working-tree"
    # Self-contained input snapshot and code hashes allow verification without bulk raw files.
    artifacts=[]
    paths=["data/sample/intervals.json","backend/app/domain/solver.py","backend/app/domain/schemas.py","backend/app/services/data.py","backend/app/services/simulator.py","backend/app/services/evidence.py","backend/app/ml/forecast.py","scripts/train_models.py","requirements.txt","requirements.lock.txt"]
    if run["forecast_model"].get("weights_sha256"):paths.append("experiments/models/carbon_model.pkl")
    for relative in paths:
        path=ROOT/relative
        if path.exists(): artifacts.append({"path":relative,"sha256":file_hash(path)})
    input_payload={"scenario":run["scenario"],"intervals":run["intervals"],"dispatch":plan["dispatch"],"batch_starts":plan["batch_starts"],"baseline_dispatch":baseline["dispatch"],"baseline_batch_starts":baseline["batch_starts"]}
    used_ids={sid for x in run["intervals"] for sid in x["source_refs"]}|{"pvgis-london-pv-model-2023","gridproof-offline-sample"}
    snapshots=[{"source_id":s["source_id"],"path":s["path"],"sha256":s["sha256"],"retrieved_utc":s["fetched_utc"],"license":s["license"],"source_url":s.get("original_url"),"attribution":s.get("attribution"),"provenance_status":s.get("provenance_status")} for s in sources()["sources"] if s["source_id"] in used_ids and s.get("sha256") and s.get("path")]
    claim={"schema_version":"1.0.0","canonicalization":"gridproof-canonical-json-v1/float-decimal-strings-9","methodology":"gridproof/location-based-operational-scenario/v1","claim_scope":{"site_hash":run["scenario"]["site_id_hash"],"from_utc":run["intervals"][0]["start_utc"],"to_utc":run["intervals"][-1]["end_utc"],"category":"modelled-grid-emissions-exposure"},"observational_status":"simulation_using_public_grid_data","source_snapshots":snapshots,"scenario_parameters":run["scenario"],"forecast_model":run["forecast_model"],"solver":plan["solver"],"baseline_id":"immediate-unmanaged-battery-idle-v1","results":{"baseline_kgco2":baseline["metrics"]["emissions_kgco2"],"plan_kgco2":plan["metrics"]["emissions_kgco2"],"difference_kgco2":baseline["metrics"]["emissions_kgco2"]-plan["metrics"]["emissions_kgco2"],"cost_gbp":plan["metrics"]["cost_gbp"],"baseline_cost_gbp":baseline["metrics"]["cost_gbp"]},"inputs":input_payload,"input_sha256":digest(input_payload),"reproduction":{"seed":42,"code_commit":commit,"selected_policy":policy,"run_id":run_id,"artifact_hashes":artifacts},"units":run["units"],"limitations":["synthetic campus; calendar PV forecast with irradiance-derived simulated replay PV and grid/curtailment recourse","not a regulatory or transferable carbon credit","average GB location-based intensity, not marginal causal abatement","historical NESO forecast issuance unverified; primary predictor is past-only","blockchain attests integrity after commitment, not physical meter truth","illustrative tariff, not actual electricity bill"]}
    claim=normalize(claim); fingerprint=digest(claim); evidence_id="evidence-"+fingerprint[:20]
    result={"evidence_id":evidence_id,"evidence":claim,"digest":"0x"+fingerprint,"sha256":fingerprint,"canonical_json":canonical_bytes(claim).decode(),**envelope(run["date"])}
    put(evidence_id,"evidence",result)
    path=ROOT/"data/processed/evidence"/(evidence_id+".json");path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    return result

def _number_fields(value):
    """Only typed input schema numeric fields are converted; id/timestamps stay strings."""
    numeric={"solar_kwp","battery_capacity_kwh","soc_initial_fraction","soc_min_fraction","soc_max_fraction","charge_kw","discharge_kw","eta_charge","eta_discharge","max_grid_import_kw","charger_station_kw","energy_kwh","max_kw","ci_actual_g_per_kwh","ci_forecast_g_per_kwh","neso_historical_forecast_g_per_kwh","fixed_load_kwh","pv_available_kwh","pv_forecast_kwh","solar_outcome_kwh","tariff_gbp_per_kwh","shortwave_radiation_w_per_m2","grid_import_kwh","grid_import_forecast_kwh","pv_used_forecast_kwh","battery_charge_kwh","battery_discharge_kwh","soc_start_kwh","soc_end_kwh","ev_charge_kwh","batch_load_kwh","pv_used_kwh","pv_curtail_kwh","export_kwh"}
    if isinstance(value,list): return [_number_fields(x) for x in value]
    if isinstance(value,dict):
        return {k:float(v) if k in numeric and v is not None else [float(x) for x in v] if k=="ev_by_job_kwh" else _number_fields(v) for k,v in value.items()}
    return value

def verify_evidence(evidence,expected_digest,check_local_files=True):
    actual=digest(evidence); expected=expected_digest.removeprefix("0x").lower()
    errors=[]; warnings=[]
    if actual!=expected: errors.append("Evidence SHA256 differs from expected digest")
    if evidence.get("schema_version")!="1.0.0" or evidence.get("canonicalization")!="gridproof-canonical-json-v1/float-decimal-strings-9": errors.append("Unsupported evidence schema/canonicalization")
    if evidence.get("methodology")!="gridproof/location-based-operational-scenario/v1": errors.append("Unsupported methodology")
    if evidence.get("observational_status")!="simulation_using_public_grid_data": errors.append("Unsupported observational status")
    if evidence.get("claim_scope",{}).get("category")!="modelled-grid-emissions-exposure": errors.append("Unsupported claim category")
    try:
        inputs=evidence["inputs"]
        if digest(inputs)!=evidence["input_sha256"]: errors.append("Input sub-bundle SHA256 mismatch")
        typed=_number_fields(inputs); scenario=Scenario.model_validate(typed["scenario"])
        if len(typed["intervals"])!=48: errors.append("Expected 48 source intervals")
        for key,starts in [("dispatch","batch_starts"),("baseline_dispatch","baseline_batch_starts")]:
            if len(typed[key])!=48: errors.append("Expected 48 dispatch intervals")
            report=check_constraints(scenario,typed[key],typed[starts])
            if not report["verified"]: errors.extend(report["violations"])
        plan=typed["dispatch"]; baseline=typed["baseline_dispatch"]
        results=evidence["results"]
        recomputed={"plan_kgco2":sum(x["grid_import_kwh"]*x["ci_actual_g_per_kwh"] for x in plan)/1000,"baseline_kgco2":sum(x["grid_import_kwh"]*x["ci_actual_g_per_kwh"] for x in baseline)/1000,"cost_gbp":sum(x["grid_import_kwh"]*x["tariff_gbp_per_kwh"] for x in plan),"baseline_cost_gbp":sum(x["grid_import_kwh"]*x["tariff_gbp_per_kwh"] for x in baseline)}
        recomputed["difference_kgco2"]=recomputed["baseline_kgco2"]-recomputed["plan_kgco2"]
        for key,val in recomputed.items():
            claimed=float(results[key])
            if not math.isfinite(claimed) or not math.isfinite(val) or abs(val-claimed)>1e-5: errors.append(f"Recomputed {key} differs from finite claim")
        # Ensure dispatch uses identical fixed load, PV, CI, tariff and source inputs.
        for key in ["dispatch","baseline_dispatch"]:
            for source,slot in zip(typed["intervals"],typed[key]):
                for name in ["start_utc","end_utc","fixed_load_kwh","pv_available_kwh","ci_actual_g_per_kwh","ci_forecast_g_per_kwh","tariff_gbp_per_kwh"]:
                    if source[name]!=slot[name]: errors.append(f"Different {name} input in {key}")
        scope=evidence["claim_scope"]
        if scope["site_hash"]!=scenario.site_id_hash or scope["from_utc"]!=plan[0]["start_utc"] or scope["to_utc"]!=plan[-1]["end_utc"]: errors.append("Claim scope differs from reconstructed scenario")
        if check_local_files:
            for artifact in evidence["source_snapshots"]+evidence["reproduction"]["artifact_hashes"]:
                path=(ROOT/artifact["path"]).resolve()
                if ROOT.resolve() not in path.parents: errors.append("Artifact path outside workspace");continue
                if path.exists():
                    if file_hash(path)!=artifact["sha256"]: errors.append(f"Local artifact digest mismatch: {artifact['path']}")
                else: warnings.append(f"Artifact not available locally: {artifact['path']}")
    except (KeyError,ValueError,TypeError,IndexError) as e: errors.append(f"Invalid evidence content: {e}")
    return {"status":"VERIFIED" if not errors else "HASH_MISMATCH" if actual!=expected else "INVALID_EVIDENCE","verified":not errors,"digest":"0x"+actual,"expected_digest":"0x"+expected,"errors":errors,"warnings":warnings,"checks":{"digest":actual==expected,"metrics_reproduced":not errors,"physical_constraints_reconstructed":not errors},"trust_boundary":"Integrity and modeled arithmetic only; no real-world emissions certification",**envelope(evidence.get("claim_scope",{}).get("from_utc","")[:10] or None)}
