"use client";
import {Area, AreaChart, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis} from "recharts";
import type {Plan} from "@/lib/api";
import {clock} from "@/lib/api";

const tooltipStyle={backgroundColor:"#102031",border:"1px solid #34445a",borderRadius:6,fontSize:11,color:"#e8eef6"};
const axis={stroke:"#7e93aa",fontSize:10,tickLine:false,axisLine:false};
export function CarbonChart({plan}: {plan: Plan}) {
  const data=plan.dispatch.map(s=>({...s,time:clock(s.start_utc)}));
  return <div className="chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={data} margin={{top:12,right:10,bottom:0,left:-18}}>
    <CartesianGrid stroke="#233146" vertical={false} strokeDasharray="3 4"/>
    <XAxis dataKey="time" interval={7} {...axis}/><YAxis {...axis}/>
    <Tooltip contentStyle={tooltipStyle}/>
    <Area isAnimationActive={false} name="Actual · gCO₂/kWh" dataKey="ci_actual_g_per_kwh" stroke="#89e3c4" fill="#89e3c4" fillOpacity={.08} strokeWidth={2}/>
    <Line isAnimationActive={false} name="Past-only forecast · gCO₂/kWh" dataKey="ci_forecast_g_per_kwh" stroke="#68a9ff" strokeWidth={1.5} strokeDasharray="5 4" dot={false}/>
  </ComposedChart></ResponsiveContainer></div>;
}
export function DispatchChart({plan}: {plan: Plan}) {
  const data=plan.dispatch.map(s=>({time:clock(s.start_utc),fixed:s.fixed_load_kwh*2,ev:s.ev_charge_kwh*2,batch:s.batch_load_kwh*2,solar:s.pv_used_kwh*2,import:s.grid_import_kwh*2}));
  return <div className="chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={data} margin={{top:12,right:10,bottom:0,left:-18}}>
    <CartesianGrid stroke="#233146" vertical={false} strokeDasharray="3 4"/><XAxis dataKey="time" interval={7} {...axis}/><YAxis {...axis}/><Tooltip contentStyle={tooltipStyle}/>
    <Area isAnimationActive={false} name="Fixed load · kW" dataKey="fixed" stackId="demand" stroke="#5d7293" fill="#5d7293" fillOpacity={.4}/>
    <Area isAnimationActive={false} name="EV · kW" dataKey="ev" stackId="demand" stroke="#89e3c4" fill="#89e3c4" fillOpacity={.55}/>
    <Area isAnimationActive={false} name="Batch · kW" dataKey="batch" stackId="demand" stroke="#68a9ff" fill="#68a9ff" fillOpacity={.5}/>
    <Line isAnimationActive={false} name="Solar · kW (simulated)" dataKey="solar" stroke="#efc67d" dot={false} strokeWidth={2}/>
    <Line isAnimationActive={false} name="Grid import · kW" dataKey="import" stroke="#d9e7f7" dot={false} strokeWidth={1.5}/>
  </ComposedChart></ResponsiveContainer></div>;
}
export function BatteryChart({plan}: {plan: Plan}) {
  const data=plan.dispatch.map(s=>({time:clock(s.start_utc),soc:s.soc_start_kwh,charge:s.battery_charge_kwh*2,discharge:s.battery_discharge_kwh*2}));
  const last=plan.dispatch.at(-1);
  if(last)data.push({time:"24:00",soc:last.soc_end_kwh,charge:0,discharge:0});
  return <div className="chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={data} margin={{top:12,right:10,bottom:0,left:-18}}>
    <CartesianGrid stroke="#233146" vertical={false} strokeDasharray="3 4"/><XAxis dataKey="time" interval={7} {...axis}/><YAxis {...axis}/><Tooltip contentStyle={tooltipStyle}/>
    <Area isAnimationActive={false} name="SoC · kWh" dataKey="soc" stroke="#89e3c4" fill="#89e3c4" fillOpacity={.12} strokeWidth={2}/>
  </AreaChart></ResponsiveContainer></div>;
}
