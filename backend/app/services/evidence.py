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
from .lineage import build_lineage,verify_lineage,ANCHORS_PATH

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
    run={**run,"scenario":plan.get("scenario_parameters",run["scenario"])}
    if not plan["constraints"]["verified"] or not baseline["constraints"]["verified"]: raise ValueError("Evidence requires verified feasible baseline and plan")
    try: commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
    except (OSError,subprocess.CalledProcessError): commit="uncommitted-working-tree"
    # Self-contained input snapshot and code hashes allow verification without bulk raw files.
    artifacts=[]
    paths=["data/sample/intervals.json","backend/app/domain/solver.py","backend/app/domain/schemas.py","backend/app/services/data.py","backend/app/services/simulator.py","backend/app/services/evidence.py","backend/app/ml/forecast.py","scripts/train_models.py","requirements.txt","requirements.lock.txt"]
    if run["forecast_model"].get("weights_sha256"):
        paths.append("experiments/models_portable/carbon_model.json" if run["forecast_model"].get("artifact_format")=="portable-json" else "experiments/models/carbon_model.pkl")
    paths.extend(["backend/app/services/lineage.py","scripts/verify_evidence.py","data/trust/source_anchors.v1.json"])
    if run.get("operational_context"):
        paths.extend(["backend/app/services/readiness.py","backend/app/domain/baselines.py"])
    for relative in paths:
        path=ROOT/relative
        if path.exists(): artifacts.append({"path":relative,"sha256":file_hash(path)})
    input_payload={"scenario":run["scenario"],"intervals":run["intervals"],"dispatch":plan["dispatch"],"batch_starts":plan["batch_starts"],"baseline_dispatch":baseline["dispatch"],"baseline_batch_starts":baseline["batch_starts"]}
    necessary_ids={"neso-national-ci-2025","openmeteo-london-weather-2025"}
    snapshots=[{"source_id":s["source_id"],"path":s["path"],"sha256":s["sha256"],"retrieved_utc":s["fetched_utc"],"license":s["license"],"source_url":s.get("original_url"),"attribution":s.get("attribution"),"provenance_status":s.get("provenance_status"),
                "role":"original_input" if s["source_id"] in necessary_ids else "derived_support","required_for_lineage":s["source_id"] in necessary_ids}
               for s in sources()["sources"] if s["source_id"] in necessary_ids|{"gridproof-offline-sample"} and s.get("sha256") and s.get("path")]
    if run["forecast_model"]["version"]=="lightgbm-past-only-v1":
        anchor=json.loads(ANCHORS_PATH.read_text(encoding="utf-8"))["models"]["lightgbm-past-only-v1"]
        snapshots.append({"source_id":anchor["source_id"],"path":anchor["paths"][0],"sha256":anchor["sha256"],"retrieved_utc":None,"license":anchor["license"],"source_url":None,"attribution":"GridProof trained model using attributed NESO historical CI", "provenance_status":"fixed_trained_model","role":"decision_model","required_for_lineage":True})
    claim={"schema_version":"1.0.0","canonicalization":"gridproof-canonical-json-v1/float-decimal-strings-9","methodology":"gridproof/location-based-operational-scenario/v1","claim_scope":{"site_hash":run["scenario"]["site_id_hash"],"from_utc":run["intervals"][0]["start_utc"],"to_utc":run["intervals"][-1]["end_utc"],"category":"modelled-grid-emissions-exposure"},"observational_status":"simulation_using_public_grid_data","source_snapshots":snapshots,"scenario_parameters":run["scenario"],"forecast_model":run["forecast_model"],"solver":plan["solver"],"baseline_id":"immediate-unmanaged-battery-idle-v1","results":{"baseline_kgco2":baseline["metrics"]["emissions_kgco2"],"plan_kgco2":plan["metrics"]["emissions_kgco2"],"difference_kgco2":baseline["metrics"]["emissions_kgco2"]-plan["metrics"]["emissions_kgco2"],"cost_gbp":plan["metrics"]["cost_gbp"],"baseline_cost_gbp":baseline["metrics"]["cost_gbp"]},"inputs":input_payload,"input_sha256":digest(input_payload),"reproduction":{"seed":42,"code_commit":commit,"selected_policy":policy,"run_id":run_id,"artifact_hashes":artifacts},"units":run["units"],"limitations":["synthetic campus; calendar PV forecast with irradiance-derived simulated replay PV and grid/curtailment recourse","not a regulatory or transferable carbon credit","average GB location-based intensity, not marginal causal abatement","historical NESO forecast issuance unverified; primary predictor is past-only","blockchain attests integrity after commitment, not physical meter truth","illustrative tariff, not actual electricity bill"]}
    claim["schema_version"]="2.0.0"
    if run.get("operational_context"):
        claim["operational_context"]=run["operational_context"]
        claim["limitations"].append("Service readiness and event history are simulated; hashes do not prove wall-clock execution or an externally witnessed pre-decision commitment")
    claim["lineage"]=build_lineage(run,canonical_bytes)
    claim["source_reference_roles"]={"neso-national-ci-2025":"original_input","openmeteo-london-weather-2025":"original_input","gridproof-offline-sample":"derived_support","neso-demand-2025":"context_only","pvgis-london-pv-model-2023":"diagnostic_only"}
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

def verify_evidence(evidence,expected_digest,check_local_files=True,expected_config_digest=None):
    actual=digest(evidence); expected=expected_digest.removeprefix("0x").lower()
    errors=[]; warnings=[];artifact_checks=[]
    if actual!=expected: errors.append("Evidence SHA256 differs from expected digest")
    if evidence.get("schema_version") not in ["1.0.0","2.0.0"] or evidence.get("canonicalization")!="gridproof-canonical-json-v1/float-decimal-strings-9": errors.append("Unsupported evidence schema/canonicalization")
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
                    matched=file_hash(path)==artifact["sha256"]
                    artifact_checks.append({"path":artifact["path"],"role":artifact.get("role","reproduction_code"),"required_for_lineage":artifact.get("required_for_lineage",False),"local_status":"MATCHED" if matched else "MISMATCH"})
                    if not matched:
                        message=f"Local artifact digest mismatch: {artifact['path']}"
                        # Authentic embedded sources remain independently verifiable even
                        # when the current checkout differs from the historical producer.
                        if evidence.get("schema_version")=="2.0.0":warnings.append(message)
                        else:errors.append(message)
                else:
                    artifact_checks.append({"path":artifact["path"],"role":artifact.get("role","reproduction_code"),"required_for_lineage":artifact.get("required_for_lineage",False),"local_status":"NOT_LOCALLY_CHECKED"})
                    warnings.append(f"Artifact not available locally (not locally checked): {artifact['path']}")
        else:
            artifact_checks=[{"path":a["path"],"role":a.get("role","reproduction_code"),"local_status":"NOT_REQUESTED"} for a in evidence["source_snapshots"]+evidence["reproduction"]["artifact_hashes"]]
    except (KeyError,ValueError,TypeError,IndexError) as e: errors.append(f"Invalid evidence content: {e}")
    if evidence.get("schema_version")=="1.0.0":
        drift=[x for x in errors if x.startswith("Local artifact digest mismatch:")]
        warnings.extend("Historical artifact differs from current checkout: "+x for x in drift)
        errors=[x for x in errors if x not in drift]
    lineage=verify_lineage(evidence,ROOT,expected_config_digest)
    if evidence.get("operational_context"):
        from scripts.verify_evidence import verify_service_context
        errors.extend(verify_service_context(evidence))
    complete=not errors and lineage["verified"]
    status="VERIFIED" if complete else "HASH_MISMATCH" if actual!=expected else "INVALID_EVIDENCE" if errors or lineage["errors"] else "INTEGRITY_ONLY" if evidence.get("schema_version")=="1.0.0" else "INCOMPLETE"
    physical_errors=[x for x in errors if x!="Evidence SHA256 differs from expected digest" and not x.startswith("Local artifact digest mismatch") and not x.startswith("Artifact path")]
    return {"status":status,"verified":complete,"digest":"0x"+actual,"expected_digest":"0x"+expected,"errors":errors+lineage["errors"],"warnings":warnings+lineage["warnings"],"artifact_checks":artifact_checks,
            "levels":{"integrity":{"verified":actual==expected,"status":"VERIFIED" if actual==expected else "HASH_MISMATCH"},"source_lineage":lineage,
                                   "physical_validity":{"verified":not physical_errors,"status":"VERIFIED" if not physical_errors else "INVALID","errors":physical_errors},"onchain_attestation":{"verified":False,"status":"NOT_CHECKED","required_for_offline_verification":False}},
            "checks":{"digest":actual==expected,"metrics_reproduced":not physical_errors,"physical_constraints_reconstructed":not physical_errors,"source_lineage_reconstructed":lineage["verified"]},
            "verified_scope":"offline integrity/source-lineage/physical arithmetic only; onchain is a separate check",
            "trust_boundary":"Pinned source consistency and modeled arithmetic; no proof of upstream truth, historical publication time, optimality or real avoided emissions certification",**envelope(evidence.get("claim_scope",{}).get("from_utc","")[:10] or None)}
