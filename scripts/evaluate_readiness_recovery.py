"""Exploratory recovery study after the fixed same-deadline event failure was seen.

This tests the actual product proposal/accept path, not new independent efficacy.
Acceptance here explicitly assumes the operator can keep the car until the later
deadline. It never changes the frozen main evaluation or its failed rows.
"""
import sys,json,time,hashlib
from pathlib import Path
from unittest.mock import patch
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.audit_scheduler_competitiveness import pinned_data
from backend.app.services.data import prepare_intervals
from backend.app.services.readiness import ReadinessRequest,UpdateRequest,create_readiness,update_readiness
from backend.app.domain.schemas import Scenario

def main():
    out=ROOT/'experiments/service_readiness';frame,by_day,_=pinned_data();rows=[];started=time.perf_counter()
    # Isolated study storage: never overwrites the product's selected runs.
    with patch('backend.app.services.storage.DB',ROOT/'.runtime/recovery-study.sqlite3'):
        for date in pd.date_range('2025-09-01','2025-12-31'):
            day=date.strftime('%Y-%m-%d')
            with patch('backend.app.services.data.fixture',return_value={'intervals':by_day[day]}):
                inputs,model=prepare_intervals(day,Scenario(),frame)
            with patch('backend.app.services.readiness.prepare_intervals',return_value=(inputs,model)):
                run=create_readiness(ReadinessRequest(date=day))
                event=UpdateRequest(run_id=run['run_id'],at_slot=16,job_id='fleet-a',energy_kwh=30,deadline_slot=20)
                initial=update_readiness(event)
                row={'date':day,'initial_accepted':initial['status']=='ready','accepted_proposed_deadline':None,'recovery_completed':False,'extra_hours':0.,'required_kwh':68.,'delivered_kwh':62.,'unserved_kwh':6.}
                final=initial
                if initial['status']!='ready':
                    recovery=initial['diagnostics'].get('recovery')
                    if recovery:
                        row['accepted_proposed_deadline']=recovery['deadline_slot']
                        row['extra_hours']=(recovery['deadline_slot']-20)*.5
                        final=update_readiness(event.model_copy(update={'deadline_slot':recovery['deadline_slot']}))
                if final['status']=='ready':
                    plan=final['plans']['peak_aware']
                    row['recovery_completed']=all(j['shortfall_kwh']<1e-5 for j in final['service'])
                    row['delivered_kwh']=sum(x['ev_charge_kwh']+x['batch_load_kwh'] for x in plan['dispatch'])
                    row['unserved_kwh']=max(0,68-row['delivered_kwh'])
                rows.append(row)
    df=pd.DataFrame(rows);df.to_csv(out/'recovery_results.csv',index=False)
    result={'study':'Exploratory after observing main-study failures; operator acceptance of later departure assumed, not free improvement',
            'attempts':len(df),'original_deadline_accepted':int(df.initial_accepted.sum()),'completed_with_accepted_extension':int(df.recovery_completed.sum()),
            'extension_hours_among_rejected':df.loc[~df.initial_accepted,'extra_hours'].describe().to_dict(),
            'wall_seconds':time.perf_counter()-started,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'controller_sha256':hashlib.sha256((ROOT/'backend/app/services/readiness.py').read_bytes()).hexdigest()}
    (out/'recovery_summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

if __name__=='__main__':main()
