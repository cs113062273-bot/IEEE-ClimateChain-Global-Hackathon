"""Render Phase2 figures and independently check summary/legacy calculations."""
from __future__ import annotations
import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/"experiments/competition_v2"

def main():
    report=json.loads((OUT/"summary.json").read_text(encoding="utf-8"))
    if report["requested_test_days"]!=122 or report["completed_test_days"]!=122:raise ValueError("Full122-day benchmark required before final reporting")
    daily=pd.read_csv(OUT/"daily_results.csv");summaries={x["policy"]:x for x in report["policies"]}
    checks=[]
    for policy,group in daily.groupby("policy"):
        paired=group.loc[group.paired_comparison_eligible]
        if len(paired):
            mean=float((100*(paired.baseline_emissions_kgco2-paired.emissions_kgco2)/paired.baseline_emissions_kgco2).mean())
            aggregate=float(100*(paired.baseline_emissions_kgco2.sum()-paired.emissions_kgco2.sum())/paired.baseline_emissions_kgco2.sum())
            if abs(mean-summaries[policy]["mean_daily_difference_percent"])>1e-9 or abs(aggregate-summaries[policy]["aggregate_difference_percent"])>1e-9:raise ValueError("Independent summary arithmetic mismatch: "+policy)
            checks.append({"policy":policy,"mean_daily_difference_percent":mean,"aggregate_difference_percent":aggregate,"status":"recomputed_from_raw_csv"})
    legacy=pd.read_csv(ROOT/"experiments/replay_results.csv");mapping={"immediate":"immediate","cost-first":"cost_first_no_ci","carbon-first":"carbon_lightgbm","hybrid":"hybrid_lightgbm","oracle":"oracle_carbon"};diffs=[]
    for _,row in legacy.iterrows():
        current=daily.loc[(daily.date==row.date)&(daily.policy==mapping[row.policy])].iloc[0]
        diffs.append({"date":row.date,"legacy_policy":row.policy,"new_policy":mapping[row.policy],"emissions_abs_delta_kgco2":abs(current.emissions_kgco2-row.emissions_kgco2),"cost_abs_delta_gbp":abs(current.cost_gbp-row.cost_gbp)})
    maximum_emissions=max(x["emissions_abs_delta_kgco2"] for x in diffs);maximum_cost=max(x["cost_abs_delta_gbp"] for x in diffs)
    if maximum_emissions>1e-6 or maximum_cost>1e-6:raise ValueError("Legacy24-day policy numeric compatibility failed")
    audit={"summary_checks":checks,"legacy_24day_comparison":{"rows":len(diffs),"max_emissions_delta_kgco2":maximum_emissions,"max_cost_delta_gbp":maximum_cost,"tolerance":1e-6},"original_24day_hashes":[{"path":"experiments/"+p,"sha256":hashlib.sha256((ROOT/"experiments"/p).read_bytes()).hexdigest()} for p in ["replay_results.csv","baseline_comparison.csv","robustness.csv","benchmark_summary.json"]],"report_script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    ablations=[]
    for model_policy,simple_policy in [("hybrid_lightgbm","hybrid_seasonal"),("peak_aware_lightgbm","peak_aware_seasonal")]:
        model=daily.loc[daily.policy==model_policy].sort_values("date").reset_index(drop=True);simple=daily.loc[daily.policy==simple_policy].sort_values("date").reset_index(drop=True)
        if list(model.date)!=list(simple.date):raise ValueError("Forecast ablation day mismatch")
        delta=model.difference_percent.to_numpy()-simple.difference_percent.to_numpy();n=len(delta);rng=np.random.default_rng(42)
        idx=rng.integers(0,n,(2000,n));means=delta[idx].mean(axis=1);starts=rng.integers(0,n,(2000,int(np.ceil(n/7))));blocks=((starts[:,:,None]+np.arange(7))%n).reshape(2000,-1)[:,:n];blockmeans=delta[blocks].mean(axis=1)
        ablations.append({"model_policy":model_policy,"simple_policy":simple_policy,"paired_days":n,"mean_daily_improvement_delta_percentage_points":float(delta.mean()),"iid_95ci_percentage_points":[float(np.quantile(means,.025)),float(np.quantile(means,.975))],"circular7day_95ci_percentage_points":[float(np.quantile(blockmeans,.025)),float(np.quantile(blockmeans,.975))],"mean_emissions_difference_kgco2_model_minus_simple":float((model.emissions_kgco2-simple.emissions_kgco2).mean()),"mean_cost_difference_gbp_model_minus_simple":float((model.cost_gbp-simple.cost_gbp).mean()),"mean_peak_difference_kw_model_minus_simple":float((model.peak_grid_kw-simple.peak_grid_kw).mean())})
    (OUT/"paired_forecast_ablation.json").write_text(json.dumps(ablations,indent=2),encoding="utf-8")
    pd.DataFrame(diffs).to_csv(OUT/"legacy_numeric_compatibility.csv",index=False)
    (OUT/"independent_report_audit.json").write_text(json.dumps(audit,indent=2),encoding="utf-8")
    assets=OUT/"figures";assets.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.spines.top":False,"axes.spines.right":False,"figure.facecolor":"white","axes.facecolor":"white"})
    policies=["immediate","cost_first_no_ci","hybrid_latest","hybrid_seasonal","hybrid_lightgbm","peak_aware_lightgbm","peak_first_no_forecasts","peak_aware_perfect_ci_matched"]
    labels=["Immediate","Cost-first\n(no CI)","Latest\nhybrid","Seasonal\nhybrid","LightGBM\nhybrid","Peak-aware\nLightGBM","Peak-first\n(no forecasts)","Perfect CI\nmatched peak-aware"]
    colors=["#7a8da3","#b594f4","#6596cc","#64b599","#3986d3","#174c7b","#d4a33d","#bd7373"]
    fig,axes=plt.subplots(1,3,figsize=(15.5,4.8))
    for ax,field,title,unit in zip(axes,["mean_emissions_kgco2","mean_cost_gbp","mean_peak_grid_kw"],["Modeled location-based exposure","Illustrative tariff expense","Realized daily peak imports"],["kgCO2/day","GBP/day","kW"]):
        ax.bar(np.arange(len(policies)),[summaries[p][field] for p in policies],color=colors);ax.set_xticks(np.arange(len(policies)),labels,rotation=50,ha="right");ax.set_ylabel(unit);ax.set_title(title,pad=10);ax.grid(axis="y",alpha=.16);ax.set_axisbelow(True)
    fig.suptitle("122 locked UTC days · identical jobs/assets · simulated London campus",fontsize=13)
    fig.tight_layout(rect=(0,0,1,.93));fig.savefig(assets/"carbon_cost_peak.png",dpi=180);fig.savefig(assets/"carbon_cost_peak.svg");plt.close(fig)
    selected=daily.loc[daily.policy.isin(["hybrid_lightgbm","peak_aware_lightgbm","peak_first_no_forecasts"])]
    fig,axes=plt.subplots(2,1,figsize=(12,6),sharex=True)
    for policy,color,label in [("hybrid_lightgbm","#3986d3","Original hybrid"),("peak_aware_lightgbm","#174c7b","Peak-aware hybrid"),("peak_first_no_forecasts","#d4a33d","Peak-first, no forecasts")]:
        group=selected.loc[selected.policy==policy].sort_values("date");dates=pd.to_datetime(group.date)
        axes[0].plot(dates,group.difference_percent,label=label,color=color,linewidth=1.25);axes[1].plot(dates,group.peak_grid_kw,color=color,linewidth=1.25)
    axes[0].axhline(0,color="#bd7373",linestyle="--",linewidth=1);axes[0].set_ylabel("Exposure difference vs immediate (%)");axes[0].legend(loc="upper right",ncol=3,fontsize=9);axes[1].set_ylabel("Daily peak imports (kW)")
    for ax in axes:ax.grid(alpha=.16)
    fig.suptitle("Failure days remain visible · positive difference means lower modeled exposure")
    fig.tight_layout();fig.savefig(assets/"daily_tradeoffs.png",dpi=180);fig.savefig(assets/"daily_tradeoffs.svg");plt.close(fig)
    tradeoff=report["tradeoff_grid"]
    fig,(ax,key_ax)=plt.subplots(1,2,figsize=(13,6),gridspec_kw={"width_ratios":[1.45,1]})
    scatter=ax.scatter([x["mean_cost_gbp"] for x in tradeoff],[x["mean_emissions_kgco2"] for x in tradeoff],c=[x["mean_peak_grid_kw"] for x in tradeoff],cmap="viridis",s=85,edgecolor="#263849",linewidth=.6)
    # Near-identical policy points share a short label; the key keeps all exact values.
    groups=[]
    for i,x in enumerate(tradeoff,1):
        near=next((g for g in groups if abs(x["mean_cost_gbp"]-g["x"])<.025 and abs(x["mean_emissions_kgco2"]-g["y"])<.025),None)
        if near:near["ids"].append(i)
        else:groups.append({"x":x["mean_cost_gbp"],"y":x["mean_emissions_kgco2"],"ids":[i]})
    for g in groups:ax.annotate("/".join(map(str,g["ids"])),(g["x"],g["y"]),xytext=(7,8),textcoords="offset points",fontsize=9,bbox={"facecolor":"white","alpha":.8,"edgecolor":"none","pad":1})
    fig.colorbar(scatter,ax=ax,label="Mean daily peak imports (kW)",fraction=.05,pad=.04)
    ax.set_xlabel("Illustrative mean GBP/day");ax.set_ylabel("Mean modeled kgCO2/day");ax.grid(alpha=.15)
    key_ax.axis("off")
    cells=[[str(i),x["policy"].replace("carbon","c=").replace("_peak",", p="),f"{x['mean_emissions_kgco2']:.3f}",f"{x['mean_cost_gbp']:.3f}",f"{x['mean_peak_grid_kw']:.2f}"] for i,x in enumerate(tradeoff,1)]
    table=key_ax.table(cellText=cells,colLabels=["ID","Weights","kg/day","GBP/day","Peak kW"],loc="center",cellLoc="center",colWidths=[.09,.29,.2,.21,.21])
    table.auto_set_font_size(False);table.set_fontsize(9);table.scale(1,1.8)
    for (row,col),cell in table.get_celld().items():
        cell.set_edgecolor("#d8e0e8")
        if row==0:cell.set_facecolor("#edf2f7")
    fig.suptitle("Fixed exploratory weight grid · no test-best deployment selection",fontsize=14)
    fig.tight_layout(rect=(0,0,1,.95));fig.savefig(assets/"weight_tradeoff_grid.png",dpi=180);fig.savefig(assets/"weight_tradeoff_grid.svg");plt.close(fig)
    print(json.dumps({"full_days":122,"independent_summary_arithmetic":"passed","legacy_numeric_comparison":audit["legacy_24day_comparison"],"figures":str(assets)},indent=2))

if __name__=="__main__":main()
