from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json, hashlib
import numpy as np
import pandas as pd
from backend.app.domain.solver import validate_inputs

ROOT=Path(__file__).resolve().parents[3]
UNITS={"energy":"kWh/30-minute interval","power":"kW","carbon_intensity":"gCO2/kWh","emissions":"kgCO2","tariff":"GBP/kWh (illustrative)","cost":"GBP (illustrative)","soc":"kWh","time":"UTC"}

def utcnow(): return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")

def sources():
    path=ROOT/"data/manifests/sources.json"
    if not path.exists(): raise ValueError("Source manifest unavailable. Run acquisition scripts.")
    value=json.loads(path.read_text(encoding="utf-8-sig"))
    value=value if isinstance(value,dict) else {"sources":value}
    for item in value["sources"]:
        checks=[]
        if item.get("path"):
            asset=ROOT/item["path"]
            checks.append({"path":item["path"],"status":"hash_matches" if asset.exists() and snapshot_digest(asset)==item.get("sha256") else "hash_mismatch" if asset.exists() else "unavailable"})
        item["current_local_checks"]=checks
        item["current_local_status"]="verified" if checks and all(c["status"]=="hash_matches" for c in checks) else "unavailable" if not checks or all(c["status"]=="unavailable" for c in checks) else "mismatch"
    return value

def fixture():
    path=ROOT/"data/sample/intervals.json"
    if not path.exists(): raise ValueError("No authenticated downloaded fixture found. Run scripts/build_snapshot.py.")
    return json.loads(path.read_text(encoding="utf-8-sig"))

def available_dates():
    try:
        values=fixture()["intervals"]
        counts={}
        for x in values: counts[x["start_utc"][:10]]=counts.get(x["start_utc"][:10],0)+1
        return sorted(k for k,v in counts.items() if v==48)
    except (ValueError,KeyError): return []

def ci_frame():
    path=ROOT/"data/processed/neso_ci_2025.csv"
    if path.exists(): frame=pd.read_csv(path)
    else:
        small=fixture()
        path=ROOT/"data/sample/ci_history.csv"
        if path.exists(): frame=pd.read_csv(path)
        else: frame=pd.DataFrame(small.get("history_intervals",[])+small["intervals"])
    aliases={"datetime":"start_utc","from":"start_utc","actual":"grid_ci_actual_g_per_kwh","forecast":"grid_ci_forecast_g_per_kwh"}
    for old,new in aliases.items():
        if new not in frame.columns and old in frame.columns: frame=frame.rename(columns={old:new})
    if "start_utc" not in frame or "grid_ci_actual_g_per_kwh" not in frame: raise ValueError("CI schema missing timestamps or actual field")
    frame["start_utc"]=pd.to_datetime(frame.start_utc,utc=True)
    if frame.start_utc.duplicated().any() or not frame.start_utc.is_monotonic_increasing:
        # Sample history and windows may overlap; never hide source-quality issues in full input.
        if (ROOT/"data/processed/neso_ci_2025.csv").exists(): raise ValueError("CI source has duplicate/out-of-order timestamps")
        frame=frame.drop_duplicates("start_utc").sort_values("start_utc")
    frame["grid_ci_actual_g_per_kwh"]=pd.to_numeric(frame.grid_ci_actual_g_per_kwh,errors="coerce")
    return frame.set_index("start_utc")

def forecast_day(date,frame=None):
    """Frozen midnight issue. Future outcomes are never inspected by predictor."""
    from backend.app.ml.forecast import predict_day
    frame=ci_frame() if frame is None else frame
    issue=pd.Timestamp(date,tz="UTC")
    past=frame.loc[frame.index<issue]
    if past.empty: raise ValueError("No past-only observations preceding decision midnight")
    values,method=predict_day(past,issue)
    training=["2025-01-08T00:00:00Z","2025-06-30T23:30:00Z"] if method=="lightgbm-past-only-v1" else None
    from backend.app.ml.forecast import model_artifact_path
    weights=model_artifact_path()
    return values,{"version":method,"training_window_utc":training,"selection_end":"2025-08-31T23:30:00Z" if method=="lightgbm-past-only-v1" else None,"selection_usable_from":"2025-09-01T00:00:00Z" if method=="lightgbm-past-only-v1" else None,"weights_sha256":snapshot_digest(weights) if method=="lightgbm-past-only-v1" and weights.exists() else None,"artifact_format":"portable-json" if method=="lightgbm-past-only-v1" and weights.suffix==".json" else "local-pickle" if method=="lightgbm-past-only-v1" else "rule-based","decision_time":issue.isoformat().replace("+00:00","Z"),"latest_observation":past.index.max().isoformat().replace("+00:00","Z"),"feature_policy":"only carbon observations strictly before decision_time and calendar; no future actual/weather/demand; validation-selected model usable only from September1","uncertainty":None,"historical_neso_forecast":"secondary; publication/issuance time unverified","availability_assumption":"Past actual CI timestamps assumed available at issue; historical publication latency not independently archived"}

def prepare_intervals(date,scenario,frame=None):
    raw=[x for x in fixture()["intervals"] if x["start_utc"][:10]==date]
    if len(raw)!=48:
        frame=ci_frame() if frame is None else frame
        joined=ROOT/"data/processed/intervals_2025.csv"
        if joined.exists():
            full=pd.read_csv(joined)
            raw=full.loc[full.start_utc.str.startswith(date)].replace({np.nan:None}).to_dict("records")
    if len(raw)!=48:
        frame=ci_frame() if frame is None else frame
        selected=frame.loc[(frame.index>=pd.Timestamp(date,tz="UTC"))&(frame.index<pd.Timestamp(date,tz="UTC")+pd.Timedelta(days=1))]
        if len(selected)!=48: raise ValueError("Selected day missing 48 actual half-hour outcomes")
        raw=[{"start_utc":ts.isoformat().replace("+00:00","Z"),"end_utc":(ts+pd.Timedelta(minutes=30)).isoformat().replace("+00:00","Z"),"grid_ci_actual_g_per_kwh":float(r.grid_ci_actual_g_per_kwh),"grid_ci_forecast_g_per_kwh":None if pd.isna(r.get("grid_ci_forecast_g_per_kwh")) else float(r.grid_ci_forecast_g_per_kwh),"source_refs":["neso-national-ci-2025"],"quality_flags":["national_ci"]} for ts,r in selected.iterrows()]
    predictions,model=forecast_day(date,frame)
    day=datetime.fromisoformat(date); year_day=day.timetuple().tm_yday
    # Hypothetical deterministic PV assumption available at issue time. No retrospective weather input.
    daylight=12+4*np.sin(2*np.pi*(year_day-80)/365); sunrise=12-daylight/2
    season=.58+.20*np.sin(2*np.pi*(year_day-80)/365)
    intervals=[]
    for t,x in enumerate(raw):
        hour=(t+.5)*.5
        solar=scenario.solar_kwp*.5*season*max(0,float(np.sin(np.pi*(hour-sunrise)/daylight))) if sunrise<=hour<=sunrise+daylight else 0
        radiation=x.get("shortwave_radiation_w_per_m2")
        if radiation is None or not np.isfinite(float(radiation)):
            raise ValueError("Historical irradiance unavailable for PV outcome replay; no fabricated solar outcome")
        outcome_solar=scenario.solar_kwp*.5*.8*max(0,min(1,float(radiation)/1000))
        fixed=.5*(6+8*(8<=hour<18)+2*(18<=hour<22))
        tariff=.12 if hour<7 else .36 if 16<=hour<20 else .23
        actual=x.get("grid_ci_actual_g_per_kwh")
        refs=x.get("source_refs")
        if isinstance(refs,str):
            try: refs=json.loads(refs)
            except json.JSONDecodeError: refs=[refs]
        flags=x.get("quality_flags",[])
        if isinstance(flags,str):
            try: flags=json.loads(flags)
            except json.JSONDecodeError: flags=[flags]
        record={"start_utc":x["start_utc"],"end_utc":x["end_utc"],"ci_actual_g_per_kwh":actual,"ci_forecast_g_per_kwh":float(predictions[t]),"neso_historical_forecast_g_per_kwh":x.get("grid_ci_forecast_g_per_kwh"),"fixed_load_kwh":fixed,"pv_available_kwh":float(solar),"pv_forecast_kwh":float(solar),"solar_outcome_kwh":float(outcome_solar),"tariff_gbp_per_kwh":tariff,"source_refs":refs or ["neso-national-ci-2025","openmeteo-london-weather-2025"],"quality_flags":list(flags)+["synthetic_campus","calendar_pv_forecast","radiation_pv_replay_outcome","illustrative_tariff"],"provenance_status":{"carbon_actual":"observed","carbon_decision":"forecast","campus_load":"synthetic","solar":"modeled","tariff":"synthetic"},"shortwave_radiation_w_per_m2":float(radiation)}
        intervals.append(record)
    validate_inputs(intervals)
    return intervals,model

def envelope(date=None):
    return {"provenance_status":{"grid_outcomes":"observed","decision_carbon":"forecast","facility":"synthetic","pv":"modeled","tariff":"synthetic"},"units":UNITS,"data_timestamp":date+"T00:00:00Z" if date else utcnow(),"claim_limit":"Modeled location-based emissions exposure; average GB intensity. No measured facility, causal avoided emissions, or tradable credit."}

def snapshot_digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
