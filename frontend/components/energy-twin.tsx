"use client";
import type {Slot} from "@/lib/api";
import {number} from "@/lib/api";

export function EnergyTwin({slot}: {slot: Slot}) {
  const batteryPower = 2 * (slot.battery_discharge_kwh - slot.battery_charge_kwh);
  const nodes = [
    {x:40,y:30,w:155,h:70,label:"Rooftop solar",detail:`${number(slot.pv_used_kwh*2)} kW · simulated`,color:"#efc67d",icon:"☀"},
    {x:365,y:30,w:155,h:70,label:"GB power grid",detail:`${number(slot.grid_import_kwh*2)} kW · import`,color:"#68a9ff",icon:"↯"},
    {x:203,y:122,w:155,h:70,label:"London campus",detail:`${number((slot.fixed_load_kwh+slot.ev_charge_kwh+slot.batch_load_kwh)*2)} kW · demand`,color:"#89e3c4",icon:"▦"},
    {x:28,y:222,w:155,h:70,label:"Battery storage",detail:`${number(slot.soc_end_kwh)} kWh · ${batteryPower>=0?"discharge":"charge"}`,color:"#89e3c4",icon:"▰"},
    {x:210,y:222,w:145,h:70,label:"EV fleet",detail:`${number(slot.ev_charge_kwh*2)} kW · scheduled`,color:"#89e3c4",icon:"ϟ"},
    {x:383,y:222,w:155,h:70,label:"Compute lab",detail:`${number(slot.batch_load_kwh*2)} kW · batch`,color:"#68a9ff",icon:"▤"},
  ];
  return <svg viewBox="0 0 560 325" role="img" aria-label={`Simulated campus: grid import ${number(slot.grid_import_kwh*2)} kW, PV ${number(slot.pv_used_kwh*2)} kW, battery state ${number(slot.soc_end_kwh)} kWh`}>
    <path className={`twin-flow ${slot.pv_used_kwh>0?"":"inactive"}`} d="M118 100 V155 H203" />
    <path className="twin-flow blue" d="M443 100 V155 H358" />
    <path className={`twin-flow ${Math.abs(batteryPower)>.01?"":"inactive"}`} d={batteryPower>=0?"M106 222 V170 H203":"M203 170 H106 V222"} />
    <path className={`twin-flow ${slot.ev_charge_kwh>0?"":"inactive"}`} d="M280 192 V222" />
    <path className={`twin-flow blue ${slot.batch_load_kwh>0?"":"inactive"}`} d="M358 170 H462 V222" />
    {nodes.map(n=><g key={n.label}><rect className="twin-node" x={n.x} y={n.y} width={n.w} height={n.h} rx="8"/><text x={n.x+12} y={n.y+27} fill={n.color} fontSize="23">{n.icon}</text><text className="twin-label" x={n.x+38} y={n.y+26}>{n.label}</text><text className="twin-detail" x={n.x+12} y={n.y+51}>{n.detail}</text></g>)}
  </svg>;
}
