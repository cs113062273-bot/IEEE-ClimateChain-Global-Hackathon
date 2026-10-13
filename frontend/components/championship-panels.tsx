"use client";
import Link from "next/link";
import {ArrowRight, ArrowDownToLine} from "lucide-react";
import {download, downloadText, number, type Comparison, type Json} from "@/lib/api";

export type OperatingPolicy=Exclude<keyof Comparison["plans"],"oracle">;
export function carbonForecastUsed(result:Comparison,selected:OperatingPolicy){return selected==="carbon_first"||((selected==="hybrid"||selected==="peak_aware")&&result.carbon_weight>0);}
export const operatingGoals=[
  {key:"carbon_first",label:"Lowest Carbon",description:"Prioritize forecast carbon exposure"},
  {key:"cost_first",label:"Lowest Cost",description:"Prioritize illustrative tariff cost"},
  {key:"peak_first",label:"Lowest Peak",description:"Minimize a conservative power envelope"},
  {key:"peak_aware",label:"Balanced",description:"Balance carbon, cost and peak demand"},
] as const;
export function policyName(key:OperatingPolicy){return operatingGoals.find(g=>g.key===key)?.label??(key==="hybrid"?"Original carbon–cost hybrid":"Immediate charging");}
export function GoldenPath({page}:{page:string}){
  return <nav className="golden-path" aria-label="60 second judge walkthrough">
    <span>60-second walkthrough</span>
    {[{step:1,href:"/dispatch",page:"dispatch",label:"Choose a goal"},{step:2,href:"/replay",page:"replay",label:"Compare schedules"},{step:3,href:"/audit",page:"audit",label:"Challenge the evidence"}].map(g=><Link key={g.step} href={g.href} aria-current={page===g.page?"step":undefined}><b>{g.step}</b>{g.label}<ArrowRight size={12}/></Link>)}
  </nav>;
}
export function GoalSelector({result,selected,onSelect}:{result:Comparison;selected:OperatingPolicy;onSelect:(key:OperatingPolicy)=>void}){
  const current=result.plans[selected],base=result.plans.immediate;
  const outcomes=[{label:"Carbon exposure",field:"emissions_kgco2",unit:"kgCO₂"},{label:"Tariff cost",field:"cost_gbp",unit:"£"},{label:"Grid peak",field:"peak_grid_kw",unit:"kW"}] as const;
  return <section className="goal-section" aria-label="Operating goal and comparison">
    <div className="goal-heading"><strong>What matters most to your campus?</strong><span>{result.date} · historical scenario · identical EV and lab work</span></div>
    <div className="goal-options">{operatingGoals.map(g=><button key={g.key} className={selected===g.key?"goal-card chosen":"goal-card"} aria-label={g.label} aria-pressed={selected===g.key} onClick={()=>onSelect(g.key)}><strong>{g.label}</strong><small>{g.description}</small></button>)}</div>
    <div className="goal-outcomes" aria-live="polite">{outcomes.map(o=>{const value=current.metrics[o.field],reference=base.metrics[o.field],reduction=reference?(reference-value)/reference*100:0;return <div key={o.field} data-testid={"goal-"+o.field}><span>{o.label}</span><strong className={reduction>=0?"green-text":"amber-text"}>{reduction>=0?"−":"+"}{number(Math.abs(reduction),2)}%</strong><small>Immediate {number(reference,2)} → {number(value,2)} {o.unit}</small></div>;})}</div>
    <p className="goal-note" data-testid="active-operating-goal"><b>{policyName(selected)}</b> · {current.constraints.verified?"Physically feasible":"Check constraints"} · {number(current.metrics.workload_kwh,1)} kWh of flexible work. Switching goals displays already computed policies; scenario changes require Run optimization. Objectives do not guarantee the lowest realized historical outcome.</p>
  </section>;
}
export function ScheduleExport({result,selected}:{result:Comparison;selected:OperatingPolicy}){
  const plan=result.plans[selected];
  function csv(){
    const columns=["run_id","date","policy","comparison_forecast_model","carbon_prediction_used_for_objective","facility_status","tariff_status","carbon_metric","start_utc","end_utc","grid_import_kwh","grid_import_kw","fixed_load_kwh","ev_charge_kwh","batch_load_kwh","battery_charge_kwh","battery_discharge_kwh","soc_start_kwh","soc_end_kwh","pv_used_kwh","ci_forecast_g_per_kwh","ci_actual_g_per_kwh","tariff_gbp_per_kwh","interval_modeled_kgco2","interval_cost_gbp"];
    const quote=(v:unknown)=>'"'+String(v??"").replaceAll('"','""')+'"';
    const rows=plan.dispatch.map(s=>[result.run_id,result.date,selected,result.forecast_model.version,carbonForecastUsed(result,selected),"simulated","illustrative","modeled grid emissions exposure",s.start_utc,s.end_utc,s.grid_import_kwh,s.grid_import_kwh*2,s.fixed_load_kwh,s.ev_charge_kwh,s.batch_load_kwh,s.battery_charge_kwh,s.battery_discharge_kwh,s.soc_start_kwh,s.soc_end_kwh,s.pv_used_kwh,s.ci_forecast_g_per_kwh,s.ci_actual_g_per_kwh,s.tariff_gbp_per_kwh,s.grid_import_kwh*s.ci_actual_g_per_kwh/1000,s.grid_import_kwh*s.tariff_gbp_per_kwh]);
    downloadText(`gridproof-${result.date}-${selected}.csv`,[columns,...rows].map(row=>row.map(quote).join(",")).join("\r\n")+"\r\n","text/csv;charset=utf-8");
  }
  const value={schema_version:"gridproof-schedule-export/v1",run_id:result.run_id,date:result.date,selected_policy:selected,forecast_model:result.forecast_model,carbon_prediction_used_for_objective:carbonForecastUsed(result,selected),scenario:plan.scenario_parameters??result.scenario,carbon_weight:result.carbon_weight,provenance_status:result.provenance_status,units:result.units,plan,claim_limit:"Historical modeled exposure; simulated campus/PV and illustrative tariff. Exported schedule is not a hardware command or proof of on-chain attestation."};
  return <div className="button-row" aria-label="Selected schedule export"><button className="btn" onClick={csv}><ArrowDownToLine size={13}/>Download schedule CSV</button><button className="btn" onClick={()=>download(`gridproof-${result.date}-${selected}.json`,value)}><ArrowDownToLine size={13}/>Download schedule JSON</button><span className="tiny">48 intervals · {policyName(selected)} · actual computed result</span></div>;
}
function object(v:Json|undefined):Record<string,Json>{return v!==null&&typeof v==="object"&&!Array.isArray(v)?v:{};}
export function EvidenceSubject({value,origin}:{value:Json;origin:string}){
  const e=object(value),scope=object(e.claim_scope),reproduction=object(e.reproduction),inputs=object(e.inputs),scenario=object(inputs.scenario);
  const rows=Array.isArray(inputs.intervals)?inputs.intervals:[],first=object(rows[0]);
  return <div className="evidence-subject" aria-label="Evidence subject"><strong>{origin==="recorded"?"Fixed release report":"Your selected schedule report"}</strong><div className="stat-list"><div className="stat-row"><span>Site</span><b>{String(scenario.site_id??scope.site_hash??"Unavailable")}</b></div><div className="stat-row"><span>UTC period</span><b>{String(scope.from_utc??"").slice(0,16)} → {String(scope.to_utc??"").slice(0,16)}</b></div><div className="stat-row"><span>Claim category</span><b>{String(scope.category??"Unavailable")}</b></div><div className="stat-row"><span>Scheduling policy</span><b data-testid="evidence-policy">{String(reproduction.selected_policy??"Unavailable")}</b></div><div className="stat-row"><span>First source-derived CI value</span><b>{number(Number(first.ci_actual_g_per_kwh),2)} gCO₂/kWh</b></div></div><p className="footnote">A source-consistent schedule is checked locally. A separate registry read checks whether this exact report is committed.</p></div>;
}
export function RegistryStory({record}:{record:Record<string,unknown>}){
  const history=record.record_history as {previous_record_id?:string|null;replaced_by_record_id?:string|null;revoked_at_unix?:number|null;reason_digest?:string|null}|undefined;
  const id=(v:string|null|undefined)=>v===undefined||v===null?"Not loaded":v==="0"?"None":`Record ${v}`;
  const status=record.status=== "REVOKED"?"Revoked":record.record_status===1?"Active":record.status==="NOT_REGISTERED"?"Not registered":"Not established";
  return <div className="registry-story" aria-label="Registry history"><div className="stat-list"><div className="stat-row"><span>Network</span><b>{record.chain_id===31337?"Local development chain":record.chain_id===11155111?"Sepolia testnet":"Unavailable"}</b></div><div className="stat-row"><span>Registry state</span><b>{status}</b></div><div className="stat-row"><span>Record ID</span><b>{String(record.record_id??"Not loaded")}</b></div><div className="stat-row"><span>Corrects previous record</span><b>{id(history?.previous_record_id)}</b></div><div className="stat-row"><span>Replaced by</span><b>{id(history?.replaced_by_record_id)}</b></div><div className="stat-row"><span>Revocation</span><b>{history?.revoked_at_unix?new Date(history.revoked_at_unix*1000).toISOString():history?.revoked_at_unix===0?"Not revoked":"Not loaded"}</b></div></div><p className="footnote">Corrections preserve prior records: authorized revoke, then linked replacement. Record IDs are registry identifiers, not version counters. No lifecycle event is invented for this report.</p></div>;
}
