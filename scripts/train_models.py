"""Frozen-train, rolling-midnight held-out evaluation; no shuffled split."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hashlib,json,pickle
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error,mean_squared_error
from backend.app.services.data import ROOT,ci_frame
from backend.app.ml.forecast import features,seasonal

def main():
    frame=ci_frame(); dates=pd.date_range("2025-01-08","2025-12-31",tz="UTC",freq="D")
    examples=[]
    for issue in dates:
        past=frame.loc[frame.index<issue]
        day=frame.loc[(frame.index>=issue)&(frame.index<issue+pd.Timedelta(days=1))]
        if len(day)!=48 or day.grid_ci_actual_g_per_kwh.isna().any(): continue
        examples.append((issue,features(past,issue),day.grid_ci_actual_g_per_kwh.to_numpy(),past,day))
    train=[x for x in examples if x[0]<pd.Timestamp("2025-07-01",tz="UTC")]
    if len(train)<90: raise ValueError("At least 90 valid training days required")
    model=LGBMRegressor(n_estimators=180,num_leaves=15,max_depth=5,learning_rate=.04,min_child_samples=60,random_state=42,n_jobs=1,deterministic=True,force_col_wise=True,verbosity=-1)
    model.fit(np.concatenate([x[1] for x in train]),np.concatenate([x[2] for x in train]))
    rows=[];day_rows=[];predictions=[]
    for split,start,end in [("validation","2025-07-01","2025-09-01"),("locked_test","2025-09-01","2026-01-01")]:
        measured={}
        for issue,X,y,past,day in examples:
            if not pd.Timestamp(start,tz="UTC")<=issue<pd.Timestamp(end,tz="UTC"): continue
            prev_day=day.index-pd.Timedelta(days=1)
            same=np.array([past.grid_ci_actual_g_per_kwh.get(ts,np.nan) for ts in prev_day])
            latest=float(past.grid_ci_actual_g_per_kwh.dropna().iloc[-1]); same=np.where(np.isfinite(same),same,latest)
            methods={"latest_known":np.full(48,latest),"same_slot_previous_day":same,"seven_day_seasonal_median":seasonal(past,issue),"lightgbm_past_only":np.clip(model.booster_.predict(X,num_threads=1),0,1500),"neso_historical_issuance_unverified":day.grid_ci_forecast_g_per_kwh.to_numpy()}
            for method,values in methods.items():
                mask=np.isfinite(values)&np.isfinite(y)
                if not mask.any(): continue
                measured.setdefault(method,[]).append((y[mask],values[mask]))
                day_rows.append({"date":issue.date().isoformat(),"split":split,"method":method,"mae_g_per_kwh":mean_absolute_error(y[mask],values[mask]),"rmse_g_per_kwh":np.sqrt(mean_squared_error(y[mask],values[mask]))})
                for t,v in enumerate(values): predictions.append({"decision_time":issue.isoformat(),"outcome_time":day.index[t].isoformat(),"split":split,"method":method,"forecast_g_per_kwh":float(v),"actual_g_per_kwh":float(y[t])})
        for method,data in measured.items():
            y=np.concatenate([x[0] for x in data]); p=np.concatenate([x[1] for x in data])
            rows.append({"split":split,"method":method,"intervals":len(y),"days":len(data),"mae_g_per_kwh":float(mean_absolute_error(y,p)),"rmse_g_per_kwh":float(np.sqrt(mean_squared_error(y,p))),"information_status":"issuance-unverified secondary" if method.startswith("neso") else "past-only primary"})
    valid={r["method"]:r["mae_g_per_kwh"] for r in rows if r["split"]=="validation"}
    selected="lightgbm_past_only" if valid["lightgbm_past_only"]<valid["seven_day_seasonal_median"] else "seven_day_seasonal_median"
    artifact={"model":model,"training_start":"2025-01-08T00:00:00Z","training_end":"2025-06-30T23:30:00Z","selection_end":"2025-08-31T23:30:00Z","usable_from":"2025-09-01T00:00:00Z","version":"lightgbm-past-only-v1" if selected=="lightgbm_past_only" else "past-only-seven-day-seasonal-median-v1","selected_method":selected,"validation_selection":"minimum validation MAE between LightGBM and seasonal median; locked test never used for choice","seed":42}
    output=ROOT/"experiments"; (output/"models").mkdir(parents=True,exist_ok=True)
    with (output/"models/carbon_model.pkl").open("wb") as handle: pickle.dump(artifact,handle)
    pd.DataFrame(rows).to_csv(output/"forecast_metrics.csv",index=False)
    pd.DataFrame(day_rows).to_csv(output/"forecast_day_metrics.csv",index=False)
    pd.DataFrame(predictions).to_csv(output/"forecast_predictions.csv",index=False)
    report={"training_days":len(train),"training_intervals":len(train)*48,"training_window":[artifact["training_start"],artifact["training_end"]],"validation_window":["2025-07-01","2025-08-31"],"usable_from":artifact["usable_from"],"locked_test_window":["2025-09-01","2025-12-31"],"selected_method":selected,"selection":artifact["validation_selection"],"source_sha256":hashlib.sha256((ROOT/"data/processed/neso_ci_2025.csv").read_bytes()).hexdigest(),"metrics":rows,"uncertainty":"not calibrated; no confidence band claimed","limitations":["one GB year","national average intensity","retrospective NESO forecast issuance unverified","weather and demand intentionally excluded from predictors to prevent unavailable-information leakage"]}
    (output/"forecast_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__": main()
