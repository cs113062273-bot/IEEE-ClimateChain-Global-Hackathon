"""Audit saved evaluation rows and derive service/cost evidence without rerunning."""
import json,hashlib
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'experiments/service_readiness'
d=pd.read_csv(OUT/'daily_results.csv');s=pd.read_csv(OUT/'summary.csv')
assert len(d)==6160 and not d.duplicated(['date','case','policy']).any()
assert d[d.case=='validation'].shape[0]==60
assert (d[(d.case=='historical_protected')&(d.policy=='protected_lightgbm')].valid).all()
assert (d[(d.case=='old_plan_early_departure')].unserved_workload_kwh>0).all()
assert np.allclose(d[d.case=='demand_update_0800'].required_workload_kwh,68)
assert (d[(d.case=='demand_update_0800')&~d.valid].unserved_workload_kwh<=6.00001).all()
metadata=json.loads((OUT/'execution.json').read_text())
for path,sha in metadata['code'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
legacy=pd.read_csv(ROOT/'experiments/competitiveness_audit/daily_results.csv')
legacy=legacy[(legacy.case=='nominal')&(legacy.policy=='gridproof_lightgbm')]
same=d[d.case=='old_nominal'].merge(legacy,on='date',suffixes=('','_legacy'))
diff={k:float((same[k]-same[k+'_legacy']).abs().max()) for k in ['emissions_kgco2','cost_gbp','peak_grid_kw']}
assert len(same)==122 and max(diff.values())<1e-8
nominal=s[s.case=='historical_protected'].set_index('policy')
old=s[(s.case=='old_nominal')].iloc[0];new=nominal.loc['protected_lightgbm'];imm=nominal.loc['immediate']
comparison={
    'protected_vs_immediate_carbon_percent':100*(1-new.mean_carbon_kg/imm.mean_carbon_kg),
    'protected_vs_immediate_cost_percent':100*(1-new.mean_cost_gbp/imm.mean_cost_gbp),
    'protected_vs_immediate_peak_percent':100*(1-new.mean_peak_kw/imm.mean_peak_kw),
    'service_protection_extra_carbon_kg_per_day':new.mean_carbon_kg-old.mean_carbon_kg,
    'service_protection_extra_gbp_per_day':new.mean_cost_gbp-old.mean_cost_gbp,
    'service_protection_extra_peak_kw':new.mean_peak_kw-old.mean_peak_kw,
    'old_unserved_kwh_per_day':float(s[s.case=='old_plan_early_departure'].iloc[0].mean_unserved_kwh),
    'old_regression_max_absolute_difference':diff,
    'legacy_comparison_rows':len(same),
    'new_scenario_validity':s[s.case.isin(['shared-11kw','four-vehicle-shifts','no-storage','no-solar'])][['case','policy','attempts','valid']].to_dict('records'),
    'failed_update_rule':'retain original controls; count 6kWh unmet new demand, not zero prior delivery',
    'rows':len(d),'execution_seconds':metadata['elapsed_seconds']}
(OUT/'audit.json').write_text(json.dumps(comparison,indent=2))
labels=['Immediate','Tariff greedy','Carbon greedy','Peak heuristic','Protected\nGridProof','Seasonal\nsame solver','Latest\nsame solver']
keys=['immediate','greedy_cost','greedy_carbon','peak_heuristic','protected_lightgbm','protected_seasonal','protected_latest']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(1,3,figsize=(15,5),layout='constrained')
for ax,metric,title in zip(axes,['mean_carbon_kg','mean_cost_gbp','mean_peak_kw'],['Grid exposure · kgCO₂/day','Illustrative cost · £/day','Daily peak · kW']):
    values=[nominal.loc[k,metric] for k in keys]
    bars=ax.barh(labels,values,color=['#245de5' if k=='protected_lightgbm' else '#b8c8df' for k in keys])
    ax.invert_yaxis();ax.set_title(title,loc='left',fontweight='bold');ax.set_xlim(0,max(values)*1.18)
    ax.bar_label(bars,fmt='%.2f',padding=4,fontsize=9);ax.grid(axis='x',alpha=.13);ax.set_axisbelow(True)
fig.suptitle('Same early service. Same devices. All seven strategies deliver 62 kWh/day on all 122 days.\nPreviously inspected Sep–Dec 2025 · simulated site · not measured or causal abatement',fontsize=12,x=.01,ha='left')
fig.savefig(OUT/'matched_service.png',dpi=180);fig.savefig(OUT/'matched_service.svg');plt.close(fig)
lines=['# Service-readiness evaluation (derived)','',
       'Previously inspected historical period; new fixed synthetic scenarios are scenario generalization only. Full protocol and raw rows accompany this report.','',
       '| Case | Policy | Complete / attempted | Carbon kg/day (valid only) | Cost £/day (valid only) | Peak kW (valid only) | Unserved kWh/day |',
       '|---|---|---:|---:|---:|---:|---:|']
for _,r in s.iterrows():
    lines.append(f'| {r["case"]} | {r.policy} | {r.valid}/{r.attempts} | {r.mean_carbon_kg:.3f} | {r.mean_cost_gbp:.3f} | {r.mean_peak_kw:.3f} | {r.mean_unserved_kwh:.3f} |')
lines+=['','Unserved for a policy returning no schedule means no schedule was executed in that comparison, not a claim that zero energy was physically attainable. Rejected demand updates retain original controls and prior delivery. Invalid rows are excluded from savings comparisons. Each cost/carbon/peak mean uses only that policy’s valid days; use paired_comparisons.json for matched-policy differences.','',
        f'Execution: {metadata["elapsed_seconds"]:.2f} s; {len(d)} rows. Old 122-day peak-aware metrics reproduce within {max(diff.values()):.3g}.',
        '', '![Matched comparison](matched_service.png)']
(OUT/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps(comparison,indent=2))
