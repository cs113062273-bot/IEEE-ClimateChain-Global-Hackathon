"""Inspect public catalogue metadata before any optional load sample download."""
import argparse
import json
from acquisition import *

BASE="https://ukpowernetworks.opendatasoft.com/api/explore/v2.1/catalog/datasets/ukpn-smart-meter-consumption-lv-feeder"
PAGE="https://ukpowernetworks.opendatasoft.com/explore/dataset/ukpn-smart-meter-consumption-lv-feeder/?tab=metas"

if __name__ == "__main__":
    p=argparse.ArgumentParser();p.add_argument("--refresh",action="store_true");args=p.parse_args()
    meta=None;license_info=None;d=None
    try:
        body,meta=fetch(BASE,RAW/"ukpn_sample_metadata.json",refresh=args.refresh)
        d=json.loads(body)
        license_info=d.get("metas",{}).get("default",{}).get("license","")
        # License must be explicit and permissive; metadata availability does not grant reuse.
        allowed=any(x in str(license_info).lower() for x in ("creative commons attribution", "cc-by", "cc by", "open government licence", "open data commons"))
        if not allowed:
            record("ukpn-feeder-sample",status="restricted",original_url=BASE,source_page=PAGE,**meta,license=license_info or "Unverified; no consumption records downloaded",
                   error="Public metadata did not expose an explicitly recognized permissive sample licence",provenance_status="not_used",access_limitations="No login, no subscription, no bypass; simulated campus fallback")
        else:
            url=BASE+"/records?limit=100"
            records,record_meta=fetch(url,RAW/"ukpn_sample_records.json",refresh=args.refresh)
            data=json.loads(records); rows=data["results"]
            record("ukpn-feeder-sample",status="verified",original_url=url,source_page=PAGE,**record_meta,license=license_info,attribution="UK Power Networks",
                   row_count=len(rows),columns=list(rows[0]) if rows else [],provenance_status="aggregated_meter_sample_context_only",metadata_snapshot=meta,
                   limitations=["Optional 100-record sample, not linked to the simulated campus", "No claim of contemporaneous 2025 facility consumption"])
    except Exception as exc:
        record("ukpn-feeder-sample",status="restricted",original_url=BASE,source_page=PAGE,license=license_info or "Not verified; no consumption records downloaded",license_url=(d or {}).get("metas",{}).get("default",{}).get("license_url"),metadata_snapshot=meta,
               columns=[{"column":f.get("name"),"type":f.get("type"),"description":f.get("description")} for f in (d or {}).get("fields",[])],
               catalog_records_count=(d or {}).get("metas",{}).get("default",{}).get("records_count"),catalog_description="Description advertises10000 sample records, metadata records_count30000 at inspection; consumption inaccessible",
               error=str(exc),provenance_status="not_used",access_limitations="Metadata explicitly says register/login; recordsHTTP403. No accounts, credentials or subscription; optional source omitted")
        print(f"UKPN optional sample unavailable: {exc}")
