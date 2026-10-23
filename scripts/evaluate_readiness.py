"""Reproducible service evaluation; old benchmark files are read-only.

Run: .venv/Scripts/python.exe scripts/evaluate_readiness.py
Protocol is committed as a file before execution. No outcome-dependent selection.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,sys,time,platform
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.app.domain.schemas import Scenario
from backend.app.domain.baselines import heuristic
from backend.app.domain.solver import solve
from backend.app.ml.forecast import seasonal
from backend.app.services.data import prepare_intervals
from backend.app.services.readiness import protect,decision_view,plan_service,score_fixed
from scripts.audit_scheduler_competitiveness import pinned_data,outcome_row
from scripts.run_competition_benchmark import fingerprint


def site(spec):
    data=Scenario(peak_weight=.2).model_dump()
    data.update(site_id=spec['id'],battery_capacity_kwh=spec['battery_kwh'],max_grid_import_kw=spec['grid_kw'],
                charger_station_kw=spec['station_kw'],solar_kwp=spec['solar_kwp'])
    data['site_id_hash']='0x'+hashlib.sha256(spec['id'].encode()).hexdigest()
    data['ev_jobs']=[{'id':f'vehicle-{i+1}','arrival_slot':arrival,'deadline_slot':min(48,arrival+20),
                     'energy_kwh':energy,'max_kw':11} for i,(arrival,energy) in enumerate(spec['jobs'])]
    return protect(Scenario.model_validate(data),spec['protection_slots'])


def block_interval(values):
    v=np.asarray(values);rng=np.random.default_rng(42);n=len(v)
    draws=[]
    for _ in range(2000):
        indices=((rng.integers(0,n,size=(n+6)//7)[:,None]+np.arange(7))%n).ravel()[:n]
        draws.append(v[indices].mean())
    return [float(x) for x in np.quantile(draws,[.025,.975])]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',default='experiments/service_readiness');parser.add_argument('--days',type=int);args=parser.parse_args()
    out=ROOT/args.out;out.mkdir(parents=True,exist_ok=True)
    protocol=json.loads((ROOT/'experiments/service_readiness/protocol.json').read_text())
    frame,by_day,anchors=pinned_data();started=time.perf_counter()
    files=['backend/app/domain/solver.py','backend/app/domain/baselines.py','backend/app/services/readiness.py','scripts/evaluate_readiness.py']
    metadata={'protocol_sha256':fingerprint(protocol),'started_utc':pd.Timestamp.now(tz='UTC').isoformat(),
              'code':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},'source_anchors':anchors,
              'environment':{'python':platform.python_version(),'platform':platform.platform()},'days_limit':args.days}
    (out/'execution.json').write_text(json.dumps(metadata,indent=2))
    dates=[d.strftime('%Y-%m-%d') for d in pd.date_range('2025-09-01','2025-12-31')][:args.days]
    validation=[d.strftime('%Y-%m-%d') for d in pd.date_range('2025-07-01','2025-08-31')][:args.days]
    rows=[];excluded=[]
    def inputs_for(day,s):
        with patch('backend.app.services.data.fixture',return_value={'intervals':by_day[day]}):
            return prepare_intervals(day,s,frame)[0]
    def record(day,case,policy,s,inputs,plan,elapsed,error=None,realized=None):
        row=outcome_row(day,case,policy,s,inputs,plan,error,realized_scenario=realized)
        row['wall_seconds']=elapsed;rows.append(row)
    base=Scenario(peak_weight=.2);protected=protect(base,6)
    for day in validation:
        try:inputs=inputs_for(day,protected)
        except ValueError as exc:excluded.append({'date':day,'reason':str(exc)});continue
        start=time.perf_counter();plan=plan_service(protected,inputs)
        record(day,'validation','protected_as_available',protected,inputs,plan,time.perf_counter()-start)
    scenes=[('historical_protected',protected)]+[(s['id'],site(s)) for s in protocol['sites']]
    for case,s in scenes:
        for day in dates:
            inputs=inputs_for(day,s);issue=pd.Timestamp(day,tz='UTC');past=frame.loc[frame.index<issue]
            forecasts={'protected_lightgbm':inputs,'protected_seasonal':[{**x,'ci_forecast_g_per_kwh':float(v)} for x,v in zip(inputs,seasonal(past,issue))],
                       'protected_latest':[{**x,'ci_forecast_g_per_kwh':float(past.grid_ci_actual_g_per_kwh.dropna().iloc[-1])} for x in inputs]}
            for policy in protocol['policies']:
                signal=forecasts.get(policy,inputs);start=time.perf_counter();error=None
                if policy in ('greedy_cost','greedy_carbon','peak_heuristic'):
                    plan,error=heuristic(s,decision_view(signal),policy);plan=score_fixed(s,signal,plan)
                else:plan=plan_service(s,signal,policy='immediate' if policy=='immediate' else 'hybrid')
                record(day,case,policy,s,signal,plan,time.perf_counter()-start,error)
                if case=='historical_protected' and policy=='protected_lightgbm':
                    selected=plan
            if case=='historical_protected':
                # Original deadlines: a service regression diagnostic, not an equal-service competitor.
                old=solve(base,inputs,"hybrid",.7)
                record(day,'old_plan_early_departure','old_peak_aware',base,inputs,old,old['solver']['seconds'],realized=s)
                record(day,'old_nominal','old_peak_aware',base,inputs,old,old['solver']['seconds'])
                for stress in ('zero_actual_pv','reversed_actual_ci'):
                    perturbed=copy.deepcopy(inputs)
                    for t,x in enumerate(perturbed):
                        if stress=='zero_actual_pv':x['solar_outcome_kwh']=0
                        else:x['ci_actual_g_per_kwh']=inputs[47-t]['ci_actual_g_per_kwh']
                    for policy in ('immediate','greedy_cost','greedy_carbon','peak_heuristic','protected_lightgbm'):
                        start=time.perf_counter();error=None
                        if policy in ('greedy_cost','greedy_carbon','peak_heuristic'):
                            plan,error=heuristic(s,decision_view(perturbed),policy);plan=score_fixed(s,perturbed,plan)
                        else:plan=plan_service(s,perturbed,policy='immediate' if policy=='immediate' else 'hybrid')
                        record(day,stress,policy,s,perturbed,plan,time.perf_counter()-start,error)
                actual=protect(base,4)
                record(day,'departure_before_promise','protected_lightgbm',s,inputs,selected,selected['solver']['seconds'],realized=actual)
                payload=s.model_dump();payload['ev_jobs'][0]['energy_kwh']+=6;changed=Scenario.model_validate(payload)
                for policy in ('event_replan','keep_original_plan'):
                    start=time.perf_counter()
                    updated=plan_service(changed,inputs,prefix=selected['dispatch'][:16],starts=selected['batch_starts']) if policy=='event_replan' else selected
                    rejected=not updated.get('dispatch')
                    record(day,'demand_update_0800',policy,changed,inputs,selected if rejected else updated,time.perf_counter()-start)
                    if rejected:
                        rows[-1]['status']='infeasible_update_original_controls_retained'
                        rows[-1]['reason']=updated['solver']['message']
                    rows[-1]['update_accepted']=not rejected if policy=='event_replan' else False
        print(case,len(rows),'rows',round(time.perf_counter()-started,1),'seconds',flush=True)
        pd.DataFrame(rows).to_csv(out/'daily_results.csv',index=False)
    df=pd.DataFrame(rows);summaries=[]
    for (case,policy),g in df.groupby(['case','policy'],sort=False):
        good=g[g.valid];baseline=df[(df.case==case)&(df.policy=='immediate')&df.valid]
        pairs=good.merge(baseline,on='date',suffixes=('','_base'))
        summary={'case':case,'policy':policy,'attempts':len(g),'valid':len(good),'incomplete':int((g.unserved_workload_kwh>1e-5).sum()),
                 'mean_unserved_kwh':g.unserved_workload_kwh.mean(),'mean_delivered_kwh':g.delivered_workload_kwh.mean(),
                 'mean_carbon_kg':good.emissions_kgco2.mean(),'mean_cost_gbp':good.cost_gbp.mean(),'mean_peak_kw':good.peak_grid_kw.mean(),
                 'mean_wall_seconds':g.wall_seconds.mean(),'p95_wall_seconds':g.wall_seconds.quantile(.95),
                 'matched_valid_days':len(pairs),'carbon_improvement_percent':100*(1-pairs.emissions_kgco2.sum()/pairs.emissions_kgco2_base.sum()) if len(pairs) else None,
                 'carbon_worse_days':int((pairs.emissions_kgco2>pairs.emissions_kgco2_base+1e-5).sum())}
        summaries.append(summary)
    pd.DataFrame(summaries).to_csv(out/'summary.csv',index=False)
    ablations=[]
    for case,_ in scenes:
        selected=df[(df.case==case)&(df.policy=='protected_lightgbm')&df.valid]
        for comparison in ['protected_seasonal','protected_latest','greedy_cost','greedy_carbon','peak_heuristic']:
            paired=selected.merge(df[(df.case==case)&(df.policy==comparison)&df.valid],on='date',suffixes=('','_other'))
            for metric in ['emissions_kgco2','cost_gbp','peak_grid_kw']:
                values=(paired[metric]-paired[metric+'_other']).to_numpy()
                if len(values):ablations.append({'case':case,'other':comparison,'metric':metric,'pairs':len(values),'mean_difference':float(values.mean()),'block95':block_interval(values)})
    (out/'paired_comparisons.json').write_text(json.dumps(ablations,indent=2))
    (out/'excluded_validation.json').write_text(json.dumps(excluded,indent=2))
    df[~df.valid].to_csv(out/'failures.csv',index=False)
    metadata.update(elapsed_seconds=time.perf_counter()-started,rows=len(df),finished_utc=pd.Timestamp.now(tz='UTC').isoformat())
    (out/'execution.json').write_text(json.dumps(metadata,indent=2))
    print('Complete',len(df),'rows',metadata['elapsed_seconds'],flush=True)

if __name__=='__main__':main()
