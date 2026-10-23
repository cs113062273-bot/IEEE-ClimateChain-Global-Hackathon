"""Independent stdlib-only verifier: SHA, physical constraints, jobs and metrics.
Imports no backend implementation. Integrity is not physical meter truth.
"""
from __future__ import annotations
import argparse,base64,gzip,hashlib,io,json,math,re,statistics,zlib
from pathlib import Path
from decimal import Decimal,ROUND_HALF_EVEN,DecimalException
from datetime import datetime,timedelta,timezone

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

# Bound both encoded input allocation and decompressed/original snapshot bytes.
# The extra 64 KiB accommodates gzip headers and incompressible-data overhead.
MAX_SOURCE_BYTES=8*1024*1024
MAX_ENCODED_BODY_CHARS=4*((MAX_SOURCE_BYTES+64*1024+2)//3)

# Independent specification constants, intentionally not imported from producer.
TRANSFORM_CONFIG={
    "version":"gridproof-input-transforms-v1","interval_minutes":30,"timezone":"UTC",
    "ci_interval":"portal_datetime_is_interval_start","weather_model":"ERA5",
    "radiation_alignment":"preceding_hour_at_h_plus_1_split_constant_halfhours",
    "pv_outcome":{"formula":"kwp*0.5*0.8*clip(radiation/1000,0,1)","performance_ratio":0.8},
    "pv_decision":{"formula":"calendar-sine-v1","daylight_base_hours":12,"daylight_amplitude_hours":4,"season_base":0.58,"season_amplitude":0.2,"phase_day":80,"period_days":365},
    "fixed_load":{"formula":"0.5*(6+8*(8<=midpoint_utc_hour<18)+2*(18<=midpoint_utc_hour<22))","data_origin":"synthetic"},
    "tariff":{"formula":"0.12 if midpoint_utc_hour<7 else 0.36 if 16<=hour<20 else 0.23","data_origin":"illustrative_utc_tariff"},
    "forecast_features":"past-only-carbon-calendar-15-features-v1",
    "actual_availability_assumption":"Past actual timestamps assumed available at midnight; publication latency/revisions not archived",
}


def utc(value,allow_naive=False):
    d=datetime.fromisoformat(value.replace("Z","+00:00"))
    if d.tzinfo is None:
        if not allow_naive:raise ValueError("source timestamp has no UTC zone")
        d=d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def finite(value):
    x=float(value)
    if not math.isfinite(x):raise ValueError("nonfinite source value")
    return x


def validate_scenario(s):
    for field,minimum,maximum in [("solar_kwp",0,200),("battery_capacity_kwh",0,200),("soc_initial_fraction",0,1),("soc_min_fraction",0,1),("soc_max_fraction",0,1),("charge_kw",0,100),("discharge_kw",0,100),("max_grid_import_kw",0,300),("charger_station_kw",0,200)]:
        if not minimum<=finite(s[field])<=maximum:raise ValueError("scenario bound: "+field)
    for field in ["eta_charge","eta_discharge"]:
        if not 0<finite(s[field])<=1:raise ValueError("scenario efficiency: "+field)
    if not finite(s["soc_min_fraction"])<=finite(s["soc_initial_fraction"])<=finite(s["soc_max_fraction"]):raise ValueError("scenario SoC fractions")
    if finite(s["max_grid_import_kw"])<=0 or finite(s["charger_station_kw"])<=0:raise ValueError("positive station/grid power required")
    if not re.fullmatch(r"0x[0-9a-fA-F]{64}",s["site_id_hash"]):raise ValueError("scenario site hash")
    if len(s["ev_jobs"])>8 or len(s["batch_jobs"])>4:raise ValueError("scenario exceeds supported jobs")
    if not isinstance(s["max_batch_concurrency"],int) or not 1<=s["max_batch_concurrency"]<=8:raise ValueError("scenario batch concurrency")
    ids=[]
    for job in s["ev_jobs"]+s["batch_jobs"]:
        ids.append(job["id"])
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}",job["id"]) or not 0<finite(job["energy_kwh"])<=200:raise ValueError("scenario job identity/energy")
    if len(ids)!=len(set(ids)):raise ValueError("scenario duplicate job IDs")
    for job in s["ev_jobs"]:
        if not all(isinstance(job[k],int) for k in ["arrival_slot","deadline_slot"]):raise ValueError("integer EV slots required")
        if not 0<=job["arrival_slot"]<job["deadline_slot"]<=48 or not 0<finite(job["max_kw"])<=100 or job.get("interruptible") is not True:raise ValueError("scenario EV window/cap")
    for job in s["batch_jobs"]:
        if not all(isinstance(job[k],int) for k in ["duration_slots","earliest_start_slot","latest_end_slot"]):raise ValueError("integer batch slots required")
        if not 1<=job["duration_slots"]<=48 or not 0<=job["earliest_start_slot"]<=job["latest_end_slot"]-job["duration_slots"] or job["latest_end_slot"]>48 or job.get("contiguous") is not True:raise ValueError("scenario batch window/duration")
    if s.get("peak_cap_kw") is not None and not 0<finite(s["peak_cap_kw"])<=300:raise ValueError("scenario peak cap")
    if not 0<=finite(s.get("peak_weight",0))<=5 or not 0<finite(s.get("peak_reference_kw",60))<=300:raise ValueError("scenario peak objective")
    if s.get("peak_risk_mode","zero-pv-guard") not in ["zero-pv-guard","forecast"]:raise ValueError("scenario peak risk mode")


def portable_predict(model,features):
    """Pure stdlib traversal of pinned numeric LightGBM regression trees."""
    if model.get("format")!="gridproof-lightgbm-trees-v1" or model.get("feature_count")!=15 or model.get("objective")!="regression":
        raise ValueError("unsupported portable model format")
    values=[]
    for row in features:
        if len(row)!=15 or any(not math.isfinite(float(x)) for x in row):raise ValueError("invalid portable model features")
        prediction=0.0
        for tree in model["trees"]:
            node=tree
            while "leaf_value" not in node:
                if node.get("decision_type")!="<=":raise ValueError("unsupported categorical/model decision")
                node=node["left_child" if row[int(node["split_feature"])]<=finite(node["threshold"]) else "right_child"]
            prediction+=finite(node["leaf_value"])
        values.append(min(1500.0,max(0.0,prediction)))
    return values


def carbon_features(ci,issue):
    past=sorted((t,x["actual"]) for t,x in ci.items() if t<issue and x["actual"] is not None)
    if not past:raise ValueError("no genuine past CI values before decision")
    latest=finite(past[-1][1]);known=[finite(x[1]) for x in past]
    rows=[]
    for slot in range(48):
        target=issue+timedelta(minutes=30*slot)
        values=[slot,issue.weekday(),issue.timetuple().tm_yday,math.sin(2*math.pi*slot/48),math.cos(2*math.pi*slot/48),latest,statistics.mean(known[-48:]),statistics.mean(known[-336:])]
        for k in range(1,8):
            v=ci.get(target-timedelta(days=k),{}).get("actual")
            values.append(latest if v is None else finite(v))
        rows.append(values)
    return rows,past[-1][0]


def predict_carbon(ci,issue,method,model=None):
    features,latest_time=carbon_features(ci,issue)
    if method=="lightgbm-past-only-v1":
        if model is None:raise ValueError("necessary portable trained model is unavailable")
        if issue<utc(model["metadata"]["usable_from"]):raise ValueError("model validation selection was unavailable at decision time")
        return portable_predict(model,features),latest_time
    if method!="past-only-seven-day-seasonal-median-v1":raise ValueError("unsupported frozen forecast method")
    latest=features[0][5];values=[]
    for slot in range(48):
        target=issue+timedelta(minutes=30*slot)
        samples=[ci.get(target-timedelta(days=k),{}).get("actual") for k in range(1,8)]
        valid=[finite(v) for v in samples if v is not None]
        values.append(statistics.median(valid) if valid else latest)
    return values,latest_time


def _load_pinned(blob,anchor,root):
    if blob is not None:
        if blob.get("source_id")!=anchor["source_id"] or blob.get("encoding") not in ["base64","gzip+base64"]:raise ValueError("source identity/encoding mismatch")
        encoded=blob["body"]
        if not isinstance(encoded,str):raise ValueError("source transport body must be base64 text")
        if len(encoded)>MAX_ENCODED_BODY_CHARS:raise ValueError("encoded source snapshot exceeds supported transport size")
        body=base64.b64decode(encoded,validate=True)
        if blob["encoding"]=="gzip+base64":
            try:
                with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:body=stream.read(MAX_SOURCE_BYTES+1)
            except (OSError,EOFError,zlib.error) as exc:raise ValueError("invalid compressed source transport") from exc
        if blob.get("sha256")!=anchor["sha256"]:raise ValueError("self-reported source digest differs from trusted anchor")
    else:
        body=None
        for relative in anchor.get("paths",[]):
            path=(root/relative).resolve()
            if root.resolve() not in path.parents:raise ValueError("trusted source path outside root")
            if path.exists():
                try:
                    with path.open("rb") as stream:body=stream.read(MAX_SOURCE_BYTES+1)
                except OSError as exc:raise ValueError("pinned original source is unreadable") from exc
                break
        if body is None:return None
    if len(body)>MAX_SOURCE_BYTES:raise ValueError("source snapshot exceeds supported transport size")
    if hashlib.sha256(body).hexdigest()!=anchor["sha256"]:raise ValueError("original source bytes differ from trusted upstream digest")
    return json.loads(body)


def reconstruct_immediate(scenario):
    """Declared fair reference: earliest EVs with shared cap; earliest batches; idle battery."""
    ev=[[0.0]*48 for _ in scenario["ev_jobs"]];batch=[0.0]*48;occupancy=[0]*48;starts={}
    for j,job in enumerate(scenario["ev_jobs"]):
        remaining=finite(job["energy_kwh"])
        for t in range(job["arrival_slot"],job["deadline_slot"]):
            take=min(remaining,finite(job["max_kw"])*.5,max(0.0,finite(scenario["charger_station_kw"])*.5-sum(row[t] for row in ev)))
            ev[j][t]=take;remaining-=take
        if remaining>2e-5:raise ValueError("declared immediate EV baseline is infeasible")
    for job in scenario["batch_jobs"]:
        candidates=range(job["earliest_start_slot"],job["latest_end_slot"]-job["duration_slots"]+1)
        start=next((s for s in candidates if all(occupancy[t]<scenario["max_batch_concurrency"] for t in range(s,s+job["duration_slots"]))),None)
        if start is None:raise ValueError("declared immediate batch baseline is infeasible")
        starts[job["id"]]=start
        for t in range(start,start+job["duration_slots"]):batch[t]+=finite(job["energy_kwh"])/job["duration_slots"];occupancy[t]+=1
    return ev,batch,starts


def verify_lineage(evidence,root,expected_config_digest=None):
    """Reconstruct sources -> CI, model forecast, radiation/PV, load and tariff."""
    root=Path(root);errors=[];warnings=[]
    if evidence.get("schema_version")=="1.0.0":
        return {"verified":False,"status":"LEGACY_UNVERIFIED","errors":[],"warnings":["Legacy v1 has no independently reconstructible source lineage"],"reconstructed_fields":[]}
    lineage=evidence.get("lineage")
    if not isinstance(lineage,dict):return {"verified":False,"status":"INCOMPLETE","errors":[],"warnings":["Necessary source lineage sub-bundle missing"],"reconstructed_fields":[]}
    anchor_path=root/"data/trust/source_anchors.v1.json"
    if not anchor_path.exists():return {"verified":False,"status":"INCOMPLETE","errors":[],"warnings":["External trusted upstream anchor manifest missing; evidence cannot certify its own hashes"],"reconstructed_fields":[]}
    try:
        anchors=json.loads(anchor_path.read_text(encoding="utf-8"))
        if anchors.get("version")!="gridproof-trusted-anchors-v1":raise ValueError("unsupported external anchor version")
        if hashlib.sha256(anchor_path.read_bytes()).hexdigest()!=lineage.get("trusted_anchor_manifest_sha256"):
            raise ValueError("external anchor manifest does not match declared trusted set")
        if lineage.get("version")!="gridproof-source-lineage-v2":raise ValueError("unsupported lineage version")
        config=lineage["configuration"]
        if sha(config)!=lineage["configuration_sha256"]:raise ValueError("frozen configuration digest mismatch")
        if expected_config_digest and sha(config)!=expected_config_digest.removeprefix("0x").lower():raise ValueError("configuration differs from externally committed expected configuration")
        if sha(config["transform_config"])!=sha(TRANSFORM_CONFIG):raise ValueError("unrecognized or rewritten input transform configuration")
        scenario=evidence["inputs"]["scenario"]
        if sha(scenario)!=lineage["scenario_sha256"] or sha(config["scenario"])!=sha(scenario) or sha(evidence["scenario_parameters"])!=sha(scenario):raise ValueError("scenario differs between frozen configuration and claim inputs")
        if sha(config["forecast_model"])!=sha(evidence["forecast_model"]):raise ValueError("forecast metadata differs from frozen configuration")
        records=evidence["inputs"]["intervals"]
        if len(records)!=48:raise ValueError("lineage expects exactly 48 source intervals")
        issue=utc(records[0]["start_utc"])
        if issue.hour or issue.minute or issue.second:raise ValueError("supported forecast decision issue must be UTC midnight")
        blobs={}
        for b in lineage.get("source_blobs",[]):
            if b["source_id"] in blobs:raise ValueError("duplicate source blobs")
            blobs[b["source_id"]]=b
        sid="neso-national-ci-2025";wid="openmeteo-london-weather-2025"
        carbon=_load_pinned(blobs.get(sid),anchors["sources"][sid],root)
        weather=_load_pinned(blobs.get(wid),anchors["sources"][wid],root)
        if carbon is None or weather is None:
            return {"verified":False,"status":"INCOMPLETE","errors":[],"warnings":["Necessary original CI/weather source unavailable, including embedded and local pinned snapshots"],"reconstructed_fields":[]}
        ci={}
        for r in carbon["result"]["records"]:
            t=utc(r["datetime"],allow_naive=True)
            if t in ci:raise ValueError("duplicate original CI timestamps")
            ci[t]={"actual":None if r["actual"] is None else finite(r["actual"]),"forecast":None if r["forecast"] is None else finite(r["forecast"])}
        if weather.get("utc_offset_seconds")!=0:raise ValueError("weather source is not UTC")
        h=weather["hourly"]; radiation={utc(t,allow_naive=True):v for t,v in zip(h["time"],h["shortwave_radiation"])}
        method=evidence["forecast_model"]["version"];model=None
        if method=="lightgbm-past-only-v1":
            ma=anchors["models"][method];model=_load_pinned(lineage.get("model_blob"),ma,root)
            if model is None:return {"verified":False,"status":"INCOMPLETE","errors":[],"warnings":["Necessary pinned portable forecast model unavailable"],"reconstructed_fields":[]}
            fm=evidence["forecast_model"]
            if fm.get("weights_sha256")!=ma["sha256"] or fm.get("artifact_format")!="portable-json":raise ValueError("reported forecast weights are not the portable model actually reconstructed")
            if fm.get("training_window_utc")!=[model["metadata"]["training_start"],model["metadata"]["training_end"]]:raise ValueError("forecast training window metadata differs from pinned model")
            if fm.get("selection_usable_from")!=model["metadata"]["usable_from"] or fm.get("selection_end")!=model["metadata"]["selection_end"]:raise ValueError("forecast selection metadata differs from pinned model")
        predictions,latest_time=predict_carbon(ci,issue,method,model)
        fm=evidence["forecast_model"]
        if utc(fm["decision_time"])!=issue or utc(fm["latest_observation"])!=latest_time:raise ValueError("forecast issue/latest observation metadata does not match original history")
        if method!="lightgbm-past-only-v1" and fm.get("weights_sha256") is not None:raise ValueError("seasonal forecast unexpectedly claims trained weights")
        if method!="lightgbm-past-only-v1" and (fm.get("artifact_format")!="rule-based" or fm.get("training_window_utc") is not None or fm.get("selection_end") is not None or fm.get("selection_usable_from") is not None):raise ValueError("seasonal method metadata does not describe a rule-based forecast")
        if fm.get("uncertainty") is not None:raise ValueError("this transform/model version has no calibrated forecast uncertainty")
        selected=evidence["reproduction"]["selected_policy"]
        if selected not in ["hybrid","cost_first","carbon_first","peak_aware","peak_first"]:raise ValueError("unsupported evidence policy")
        kwp=finite(scenario["solar_kwp"]);day=issue.timetuple().tm_yday
        daylight=12+4*math.sin(2*math.pi*(day-80)/365);sunrise=12-daylight/2;season=.58+.20*math.sin(2*math.pi*(day-80)/365)
        reconstructed=[]
        for t,record in enumerate(records):
            start=issue+timedelta(minutes=30*t);end=start+timedelta(minutes=30)
            if utc(record["start_utc"])!=start or utc(record["end_utc"])!=end:raise ValueError("source record times do not match frozen UTC day")
            original=ci.get(start)
            if original is None or original["actual"] is None:raise ValueError("required original actual CI unavailable; forecast cannot replace actual")
            hour=start.replace(minute=0,second=0,microsecond=0)
            rad=finite(radiation[hour+timedelta(hours=1)])
            midpoint=(t+.5)*.5
            forecast_pv=kwp*.5*season*max(0.0,math.sin(math.pi*(midpoint-sunrise)/daylight)) if sunrise<=midpoint<=sunrise+daylight else 0.0
            outcome=kwp*.5*.8*max(0.0,min(1.0,rad/1000))
            values={"ci_actual_g_per_kwh":original["actual"],"ci_forecast_g_per_kwh":predictions[t],"neso_historical_forecast_g_per_kwh":original["forecast"],
                    "shortwave_radiation_w_per_m2":rad,"pv_forecast_kwh":forecast_pv,"solar_outcome_kwh":outcome,"pv_available_kwh":outcome,
                    "fixed_load_kwh":.5*(6+8*(8<=midpoint<18)+2*(18<=midpoint<22)),"tariff_gbp_per_kwh":.12 if midpoint<7 else .36 if 16<=midpoint<20 else .23}
            reconstructed.append(values)
            for field,value in values.items():
                actual=record.get(field)
                if value is None:
                    if actual is not None:errors.append(f"source lineage mismatch interval {t} {field}")
                elif actual is None or abs(finite(actual)-value)>1e-6:errors.append(f"source lineage mismatch interval {t} {field}")
            for key in ["dispatch","baseline_dispatch"]:
                slot=evidence["inputs"][key][t]
                for field,value in values.items():
                    expected_value=0.0 if field=="pv_forecast_kwh" and key=="dispatch" and selected=="peak_first" else value
                    actual=slot.get(field)
                    if expected_value is None:
                        if actual is not None:errors.append(f"source lineage mismatch {key} {t} {field}")
                    elif actual is None or abs(finite(actual)-expected_value)>1e-6:errors.append(f"source lineage mismatch {key} {t} {field}")
                refs=slot.get("source_refs",[])
                if sid not in refs or wid not in refs:errors.append(f"required source references missing from {key} {t}")
                status=slot.get("provenance_status",{})
                if any(status.get(k)!=v for k,v in {"carbon_actual":"observed","carbon_decision":"forecast","campus_load":"synthetic","solar":"modeled","tariff":"synthetic"}.items()):errors.append(f"rewritten observed/forecast/simulation labels {key} {t}")
                # Check decision PV allocation and nonnegative import using frozen schedule.
                net=finite(slot["fixed_load_kwh"])+finite(slot["ev_charge_kwh"])+finite(slot["batch_load_kwh"])+finite(slot["battery_charge_kwh"])-finite(slot["battery_discharge_kwh"])
                decision_pv=0.0 if key=="dispatch" and selected=="peak_first" else forecast_pv
                used=finite(slot["pv_used_forecast_kwh"]);grid=finite(slot["grid_import_forecast_kwh"])
                if used< -1e-6 or used>decision_pv+1e-6 or grid< -1e-6 or abs(grid+used-net)>2e-5:
                    errors.append(f"decision energy/PV reconstruction mismatch {key} {t}")
        if evidence.get("baseline_id")!="immediate-unmanaged-battery-idle-v1":raise ValueError("unsupported declared fair baseline")
        ev,batch,starts=reconstruct_immediate(scenario)
        if evidence["inputs"]["baseline_batch_starts"]!=starts:errors.append("baseline does not use earliest feasible batch starts")
        for t,slot in enumerate(evidence["inputs"]["baseline_dispatch"]):
            if abs(finite(slot["battery_charge_kwh"]))>2e-5 or abs(finite(slot["battery_discharge_kwh"]))>2e-5:errors.append("declared immediate baseline battery is not idle")
            if abs(finite(slot["batch_load_kwh"])-batch[t])>2e-5:errors.append("declared immediate baseline batch schedule differs")
            if any(abs(finite(slot["ev_by_job_kwh"][j])-ev[j][t])>2e-5 for j in range(len(ev))):errors.append("declared immediate baseline EV schedule differs")
        # Source snapshot descriptors must identify the same externally pinned raw bytes.
        descriptors={s["source_id"]:s for s in evidence.get("source_snapshots",[])}
        for source in [sid,wid]:
            if source not in descriptors or descriptors[source].get("sha256")!=anchors["sources"][source]["sha256"]:errors.append("necessary source snapshot descriptor differs from trusted anchor: "+source)
            elif descriptors[source].get("source_url")!=anchors["sources"][source]["source_url"] or descriptors[source].get("license")!=anchors["sources"][source]["license"]:errors.append("source attribution/URL/licence metadata differs from external anchor: "+source)
            elif descriptors[source].get("role")!="original_input" or descriptors[source].get("required_for_lineage") is not True:errors.append("necessary source role was rewritten: "+source)
        if method=="lightgbm-past-only-v1":
            ma=anchors["models"][method];descriptor=descriptors.get(ma["source_id"])
            if not descriptor or descriptor.get("sha256")!=ma["sha256"] or descriptor.get("role")!="decision_model" or descriptor.get("required_for_lineage") is not True:errors.append("necessary model snapshot descriptor differs from trusted model anchor")
    except (KeyError,ValueError,TypeError,IndexError,OverflowError) as exc:errors.append("invalid source lineage: "+str(exc))
    blob_ids=set(blobs) if "blobs" in locals() else set()
    source_checks=[{"source_id":s,"status":"RECONSTRUCTED" if not errors else "CHECK_FAILED","representation":"embedded_original_bytes" if s in blob_ids else "local_pinned_original_bytes","required_for_lineage":True} for s in ["neso-national-ci-2025","openmeteo-london-weather-2025"]]
    if locals().get("method")=="lightgbm-past-only-v1":source_checks.append({"source_id":"gridproof-carbon-model-lightgbm-v1","status":"RECONSTRUCTED" if not errors else "CHECK_FAILED","representation":"embedded_model_bytes" if lineage.get("model_blob") else "local_pinned_model_bytes","required_for_lineage":True})
    return {"verified":not errors,"status":"VERIFIED" if not errors else "MISMATCH","errors":sorted(set(errors)),"warnings":warnings,"source_checks":source_checks,
            "reconstructed_fields":["actual_ci","past_only_forecast","forecast_metadata","preceding_hour_radiation","decision_calendar_pv","realized_radiation_pv","synthetic_fixed_load","illustrative_utc_tariff","scenario_configuration","decision_energy_balance"],
            "trust_boundary":"Consistency with separately trusted HTTPS snapshot digests and fixed transforms; no proof of upstream truth, historical availability or causal avoided emissions."}

def inspect(evidence,expected,root,expected_config_digest=None,check_local_files=True):
    errors=[];warnings=[];artifact_checks=[];actual=sha(evidence);tol=2e-5
    if actual!=expected.removeprefix("0x").lower():errors.append("SHA256 mismatch")
    if evidence.get("schema_version") not in ["1.0.0","2.0.0"] or evidence.get("canonicalization")!="gridproof-canonical-json-v1/float-decimal-strings-9":errors.append("unsupported schema")
    if evidence.get("methodology")!="gridproof/location-based-operational-scenario/v1":errors.append("unsupported methodology")
    if evidence.get("observational_status")!="simulation_using_public_grid_data":errors.append("unsupported observational status")
    if evidence.get("claim_scope",{}).get("category")!="modelled-grid-emissions-exposure":errors.append("unsupported claim category")
    try:
        data=evidence["inputs"];s=data["scenario"];n=lambda obj,k:float(obj[k]);validate_scenario(s)
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
                if s.get("peak_cap_kw") is not None:
                    peak=finite(s["peak_cap_kw"])*.5
                    net=n(x,"fixed_load_kwh")+n(x,"ev_charge_kwh")+n(x,"batch_load_kwh")+n(x,"battery_charge_kwh")-n(x,"battery_discharge_kwh")
                    if n(x,"grid_import_kwh")>peak+tol:errors.append("replay peak cap")
                    if s.get("peak_risk_mode")=="zero-pv-guard" and net>peak+tol:errors.append("zero-PV peak guard")
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
        for source in (evidence["source_snapshots"]+evidence["reproduction"]["artifact_hashes"] if check_local_files else []):
            path=(root/source["path"]).resolve()
            if root.resolve() not in path.parents:errors.append("source path outside root");continue
            if not path.exists():
                warnings.append("artifact unavailable; not locally checked: "+source["path"])
                artifact_checks.append({"path":source["path"],"role":source.get("role","reproduction_code"),"required_for_lineage":source.get("required_for_lineage",False),"local_status":"NOT_LOCALLY_CHECKED"});continue
            matched=hashlib.sha256(path.read_bytes()).hexdigest()==source["sha256"]
            artifact_checks.append({"path":source["path"],"role":source.get("role","reproduction_code"),"required_for_lineage":source.get("required_for_lineage",False),"local_status":"MATCHED" if matched else "MISMATCH"})
            if not matched:
                message="source digest mismatch: "+source["path"]
                if evidence.get("schema_version")=="2.0.0":warnings.append("Current checkout artifact differs: "+message)
                else:errors.append(message)
        if not check_local_files:artifact_checks=[{"path":a["path"],"role":a.get("role","reproduction_code"),"local_status":"NOT_REQUESTED"} for a in evidence["source_snapshots"]+evidence["reproduction"]["artifact_hashes"]]
    except (KeyError,ValueError,TypeError,IndexError,ZeroDivisionError,OverflowError) as exc:errors.append("invalid content: "+str(exc))
    if evidence.get("schema_version")=="1.0.0":
        drift=[x for x in errors if x.startswith("source digest mismatch:")]
        warnings.extend("Historical artifact differs from current checkout: "+x for x in drift)
        errors=[x for x in errors if x not in drift]
    if evidence.get("operational_context"): errors.extend(verify_service_context(evidence))
    physical_errors=[x for x in errors if x!="SHA256 mismatch" and not x.startswith("source digest mismatch:") and x!="source path outside root"]
    lineage=verify_lineage(evidence,root,expected_config_digest)
    complete=not errors and lineage["verified"]
    status="VERIFIED" if complete else "HASH_MISMATCH" if actual!=expected.removeprefix("0x").lower() else "INVALID_EVIDENCE" if errors or lineage["errors"] else "INTEGRITY_ONLY" if evidence.get("schema_version")=="1.0.0" else "INCOMPLETE"
    all_errors=sorted(set(errors+lineage["errors"]))
    return {"verified":complete,"status":status,"sha256":actual,"digest":"0x"+actual,"expected_digest":expected,"errors":all_errors,"warnings":warnings+lineage["warnings"],"artifact_checks":artifact_checks,
            "levels":{"integrity":{"verified":actual==expected.removeprefix("0x").lower(),"status":"VERIFIED" if actual==expected.removeprefix("0x").lower() else "HASH_MISMATCH"},
                                   "source_lineage":lineage,"physical_validity":{"verified":not physical_errors,"status":"VERIFIED" if not physical_errors else "INVALID","errors":physical_errors},
                                   "onchain_attestation":{"verified":False,"status":"NOT_CHECKED","required_for_offline_verification":False}},
            "checks":{"digest":actual==expected.removeprefix("0x").lower(),"source_lineage_reconstructed":lineage["verified"],"physical_constraints_reconstructed":not physical_errors,"metrics_reproduced":not physical_errors},
            "verified_scope":"offline integrity/source-lineage/physical arithmetic only; onchain is a separate check",
            "trust_boundary":"Consistency with separately trusted source snapshot digests, fixed transforms and modeled arithmetic; no upstream meter truth, historical publication proof, optimality proof or real avoided emissions certification"}

def verify_service_context(evidence):
    """Independent event-prefix and readiness-envelope checks, stdlib only.

    Self-consistency is not proof that a parent digest was published in advance.
    """
    errors=[]
    try:
        context=evidence["operational_context"]
        if context["schema"]!="gridproof-service-v1":raise ValueError("unknown service schema")
        expected=json.loads(json.dumps(context["original_scenario"]))
        for job in expected["ev_jobs"]:
            job["deadline_slot"]=min(job["deadline_slot"],job["arrival_slot"]+context["protection_slots"])
        events=context["events"]; previous_slot=0
        for i,event in enumerate(events):
            at=event["at_slot"]
            if not previous_slot<at<48 or event["deadline_slot"]<=at:raise ValueError("event order/deadline")
            if sha(event["parent_scenario"])!=sha(expected):raise ValueError("parent scenario differs from preceding request")
            parent=event["parent_dispatch"]
            if len(parent)!=48 or sha(parent)!=event["parent_dispatch_sha256"]:raise ValueError("parent dispatch digest")
            child=events[i+1]["parent_dispatch"] if i+1<len(events) else evidence["inputs"]["dispatch"]
            for t in range(at):
                for field in ["battery_charge_kwh","battery_discharge_kwh","soc_start_kwh","soc_end_kwh","batch_load_kwh"]:
                    if abs(finite(parent[t][field])-finite(child[t][field]))>1e-5:raise ValueError("executed prefix changed: "+field)
                if len(parent[t]["ev_by_job_kwh"])!=len(child[t]["ev_by_job_kwh"]):raise ValueError("prefix vehicle count")
                if any(abs(finite(a)-finite(b))>1e-5 for a,b in zip(parent[t]["ev_by_job_kwh"],child[t]["ev_by_job_kwh"])):raise ValueError("executed prefix changed: EV energy")
            job=next(j for j in expected["ev_jobs"] if j["id"]==event["job_id"])
            job.update(energy_kwh=event["energy_kwh"],deadline_slot=event["deadline_slot"])
            previous_slot=at
        if context["at_slot"]!=previous_slot or sha(expected)!=sha(evidence["inputs"]["scenario"]):raise ValueError("current service request differs from event history")
        for x in evidence["inputs"]["dispatch"]:
            net=sum(finite(x[k]) for k in ["fixed_load_kwh","ev_charge_kwh","batch_load_kwh","battery_charge_kwh"])-finite(x["battery_discharge_kwh"])
            if net>finite(expected["max_grid_import_kw"])*.5+1e-5 or net< -1e-5:raise ValueError("zero-PV service envelope")
    except (KeyError,ValueError,TypeError,IndexError,StopIteration) as exc:
        errors.append("Service verification: "+str(exc))
    return errors


def main():
    parser=argparse.ArgumentParser();parser.add_argument("path");parser.add_argument("--digest");parser.add_argument("--expected-config-digest");parser.add_argument("--root",default=str(Path(__file__).resolve().parents[1]));args=parser.parse_args()
    payload=json.loads(Path(args.path).read_text(encoding="utf-8-sig"));evidence=payload.get("evidence",payload)
    expected=args.digest or payload.get("digest") or payload.get("sha256")
    if not expected:raise SystemExit("--digest required for raw evidence")
    result=inspect(evidence,expected,Path(args.root),args.expected_config_digest);print(json.dumps(result,indent=2));raise SystemExit(0 if result["verified"] else 1)
if __name__=="__main__":main()
