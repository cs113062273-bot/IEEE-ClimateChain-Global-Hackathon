"""Strict domain units: energy kWh/half-hour; power kW; timestamps UTC."""
from __future__ import annotations
from typing import Literal
import hashlib
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_default=True)

class EVJob(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    energy_kwh: float = Field(gt=0, le=200)
    arrival_slot: int = Field(ge=0, le=47)
    deadline_slot: int = Field(ge=1, le=48)
    max_kw: float = Field(gt=0, le=100)
    interruptible: Literal[True] = True
    @model_validator(mode="after")
    def window(self):
        if self.deadline_slot <= self.arrival_slot:
            raise ValueError("EV deadline must follow arrival")
        return self

class BatchJob(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    energy_kwh: float = Field(gt=0, le=200)
    duration_slots: int = Field(ge=1, le=48)
    earliest_start_slot: int = Field(ge=0, le=47)
    latest_end_slot: int = Field(ge=1, le=48)
    contiguous: Literal[True] = True
    @model_validator(mode="after")
    def window(self):
        if self.latest_end_slot-self.earliest_start_slot < self.duration_slots:
            raise ValueError("Batch window shorter than its contiguous duration")
        return self

class Scenario(StrictModel):
    site_id: str = "london-campus-hypothetical-v1"
    site_id_hash: str = "0x" + hashlib.sha256(b"london-campus-hypothetical-v1").hexdigest()
    location: str = "London, GB (hypothetical campus; national GB carbon intensity)"
    solar_kwp: float = Field(default=20, ge=0, le=200)
    battery_capacity_kwh: float = Field(default=40, ge=0, le=200)
    soc_initial_fraction: float = Field(default=.5, ge=0, le=1)
    soc_min_fraction: float = Field(default=.1, ge=0, le=1)
    soc_max_fraction: float = Field(default=.9, ge=0, le=1)
    charge_kw: float = Field(default=10, ge=0, le=100)
    discharge_kw: float = Field(default=10, ge=0, le=100)
    eta_charge: float = Field(default=.95, gt=0, le=1)
    eta_discharge: float = Field(default=.95, gt=0, le=1)
    max_grid_import_kw: float = Field(default=60, gt=0, le=300)
    peak_weight: float = Field(default=0, ge=0, le=5)
    peak_cap_kw: float | None = Field(default=None, gt=0, le=300)
    peak_reference_kw: float = Field(default=60, gt=0, le=300)
    peak_risk_mode: Literal["forecast", "zero-pv-guard"] = "zero-pv-guard"
    charger_station_kw: float = Field(default=22, gt=0, le=200)
    max_batch_concurrency: int = Field(default=1, ge=1, le=8)
    ev_jobs: list[EVJob] = Field(default_factory=lambda:[EVJob(id="fleet-a",energy_kwh=24,arrival_slot=14,deadline_slot=36,max_kw=11),EVJob(id="fleet-b",energy_kwh=18,arrival_slot=16,deadline_slot=40,max_kw=11)])
    batch_jobs: list[BatchJob] = Field(default_factory=lambda:[BatchJob(id="compute-lab",energy_kwh=20,duration_slots=4,earliest_start_slot=12,latest_end_slot=42)])
    @model_validator(mode="after")
    def bounds(self):
        if not self.soc_min_fraction <= self.soc_initial_fraction <= self.soc_max_fraction:
            raise ValueError("Initial battery SoC must be between min and max")
        if len(self.ev_jobs)>8 or len(self.batch_jobs)>4:
            raise ValueError("At most 8 EV jobs and 4 batches are supported")
        ids=[j.id for j in self.ev_jobs+self.batch_jobs]
        if len(set(ids))!=len(ids):
            raise ValueError("Job ids must be unique")
        if len(self.site_id_hash)!=66 or not self.site_id_hash.startswith("0x"):
            raise ValueError("site_id_hash must be 32-byte 0x hexadecimal")
        int(self.site_id_hash[2:],16)
        return self

class OptimizeRequest(StrictModel):
    date: str = Field(default="2025-08-12", pattern=r"^2025-\d{2}-\d{2}$")
    policy: Literal["hybrid","carbon-first","cost-first","immediate","peak-first"] = "hybrid"
    carbon_weight: float = Field(default=.7, ge=0, le=1)
    scenario: Scenario = Field(default_factory=Scenario)
    solver_time_limit_seconds: float = Field(default=10, gt=0, le=30)

class ReplayRequest(OptimizeRequest):
    dates: list[str] | None = Field(default=None,max_length=31)
    seed: Literal[42] = 42

class EvidenceRequest(StrictModel):
    run_id: str
    policy: Literal["hybrid","carbon_first","cost_first","peak_aware","peak_first"] = "hybrid"

class AttestRequest(StrictModel):
    evidence_id: str
    network: Literal["local","testnet"]
    expected_chain_id: int = 31337
