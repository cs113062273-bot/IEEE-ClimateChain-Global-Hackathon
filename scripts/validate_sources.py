"""Rehash files and validate intervals; report absent bulk assets without green success."""
import argparse
import json
from acquisition import *


def validate(require_bulk=False,write_manifest=False):
    entries=[];errors=[]
    for path in sorted((MANIFEST/"artifacts").glob("*.json")):
        item=json.loads(path.read_text(encoding="utf-8"))
        checks=[]
        for field,digest_field in [("path","sha256"),("processed_path","processed_sha256")]:
            if not item.get(field):continue
            asset=ROOT/item[field]
            if not asset.exists():
                checks.append({"path":item[field],"status":"absent_bulk_snapshot"})
                if require_bulk or item[field].startswith("data/sample/"):
                    errors.append(f"{item['source_id']}: missing {item[field]}")
            else:
                matched=sha256(asset)==item[digest_field]
                checks.append({"path":item[field],"status":"hash_matches" if matched else "hash_mismatch"})
                if not matched:errors.append(f"{item['source_id']}: hash mismatch {item[field]}")
        for stored in item.get("storage_artifacts",[]):
            asset=ROOT/stored["path"]
            if not asset.exists():
                checks.append({"path":stored["path"],"status":"absent_bulk_snapshot"})
                if require_bulk:errors.append(f"{item['source_id']}: missing {stored['path']}")
            else:
                matched=sha256(asset)==stored["sha256"]
                checks.append({"path":stored["path"],"status":"hash_matches" if matched else "hash_mismatch"})
                if not matched:errors.append(f"{item['source_id']}: hash mismatch {stored['path']}")
        if item.get("processed_path","").endswith(".csv") and (ROOT/item["processed_path"]).exists():
            rows=csv_rows(ROOT/item["processed_path"])
            result=profile(rows,item.get("granularity_minutes",30))
            item["validation_profile"]=result
            if result["duplicate_timestamps"] or result["invalid_interval_duration"] or result["out_of_order"] or result["gap_count"]:
                errors.append(f"{item['source_id']}: invalid interval index")
            if result["row_count"]!=item["row_count"]:errors.append(f"{item['source_id']}: row count mismatch")
        item["local_asset_checks"]=checks;entries.append(item)
        local_status="absent_bulk_snapshot" if any(c["status"]=="absent_bulk_snapshot" for c in checks) else "all_present" if checks else "not_downloaded"
        print(f"SOURCE AUDIT {item['source_id']}: acquisition_status={item['status']} local_assets={local_status} rows={item.get('row_count','not downloaded')} size={item.get('byte_size','n/a')} sha256={item.get('sha256','n/a')}")
    # Required source state is explicit; optional blocked UKPN does not fail core gate.
    for sid in ["neso-national-ci-2025","neso-demand-2025","openmeteo-london-weather-2025","gridproof-offline-sample"]:
        if not any(i["source_id"]==sid and i["status"]=="verified" for i in entries):errors.append(f"Required source unavailable: {sid}")
    sample_path=ROOT/"data/sample/intervals.json"
    if sample_path.exists():
        sample=json.loads(sample_path.read_text(encoding="utf-8"))
        for d in sample["metadata"]["dates"]:
            day=[r for r in sample["intervals"] if r["start_utc"][:10]==d]
            qc=profile(day)
            if len(day)!=48 or qc["gap_count"] or qc["duplicate_timestamps"]:errors.append(f"Invalid sample {d}")
    result={"schema_version":"1.0.0","checked_utc":now_utc(),"client_context_date":"2026-10-13","sources":entries,"validation_errors":errors,
            "trust_boundary":"Hashes establish local snapshot integrity; they do not authenticate provider truth, certify meter readings, or create carbon credits."}
    # Routine verification must not change a provenance manifest after attestation.
    if write_manifest:
        write_json(MANIFEST/"sources.json",result)
        write_json(MANIFEST/"validation.json",{"checked_utc":result["checked_utc"],"passed":not errors,"require_bulk":require_bulk,"errors":errors})
    if errors:raise ValueError("; ".join(errors))
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--require-bulk",action="store_true")
    p.add_argument("--write-manifest",action="store_true",help="Explicitly rebuild sources.json after acquisition; default is read-only verification")
    args=p.parse_args();validate(args.require_bulk,args.write_manifest)
