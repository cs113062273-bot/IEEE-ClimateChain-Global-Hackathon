"""Data acceptance tests: DST, UTC intervals, missingness, rate limits, offline truth."""
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acquisition import ROOT, numeric, parse_utc, profile, settlement_interval, fetch, sha256
from build_snapshot import weather_halfhour
import fetch_neso
import validate_sources


class DataQualityTests(unittest.TestCase):
    def test_dst_settlement_days(self):
        spring_start,spring_end,slots=settlement_interval("2025-03-30",46)
        self.assertEqual(slots,46)
        self.assertEqual(spring_end.isoformat(),"2025-03-30T23:00:00+00:00")
        self.assertEqual(settlement_interval("2025-10-26",50)[2],50)
        self.assertEqual(settlement_interval("2025-10-26",1)[0].isoformat(),"2025-10-25T23:00:00+00:00")
        self.assertEqual(settlement_interval("2025-10-26",50)[1].isoformat(),"2025-10-27T00:00:00+00:00")
        self.assertEqual(settlement_interval("2025-08-12",48)[2],48)
        with self.assertRaises(ValueError):settlement_interval("2025-03-30",48)

    def test_timezone_and_null_not_zero(self):
        with self.assertRaises(ValueError):parse_utc("2025-01-01T00:00")
        self.assertEqual(parse_utc("2025-01-01T08:00:00+08:00"),parse_utc("2025-01-01T00:00:00Z"))
        self.assertIsNone(numeric("null"));self.assertIsNone(numeric("NaN"));self.assertEqual(numeric("0"),0)

    def test_qc_detects_duplicate_gap_and_out_of_order(self):
        rows=[{"start_utc":"2025-01-01T01:00:00Z","end_utc":"2025-01-01T01:30:00Z","actual":None},
              {"start_utc":"2025-01-01T00:00:00Z","end_utc":"2025-01-01T00:30:00Z","actual":50},
              {"start_utc":"2025-01-01T00:00:00Z","end_utc":"2025-01-01T00:30:00Z","actual":0}]
        qc=profile(rows)
        self.assertEqual(qc["duplicate_timestamps"],1);self.assertTrue(qc["out_of_order"])
        self.assertEqual(qc["missing_count"]["actual"],1);self.assertEqual(qc["gap_count"],2)

    def test_preceding_hour_radiation_energy_alignment(self):
        weather={"2025-01-01T12:00:00Z":{"temperature_2m":10,"cloud_cover_percent":20,"wind_speed_10m_kmh":4,"shortwave_radiation_w_per_m2":100},
                 "2025-01-01T13:00:00Z":{"temperature_2m":12,"cloud_cover_percent":40,"wind_speed_10m_kmh":8,"shortwave_radiation_w_per_m2":600}}
        a=weather_halfhour(weather,parse_utc("2025-01-01T12:00:00Z"));b=weather_halfhour(weather,parse_utc("2025-01-01T12:30:00Z"))
        self.assertEqual(a["shortwave_radiation_w_per_m2"]*0.5+b["shortwave_radiation_w_per_m2"]*0.5,600)
        self.assertEqual(b["temperature_2m"],11)

    def test_rate_limit_retry_records_failure_and_never_success(self):
        error=urllib.error.HTTPError("https://example.invalid/",429,"Too Many Requests",{"Retry-After":"1"},io.BytesIO(b"rate limited"))
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            out=Path(td)/"raw.json"
            with patch("urllib.request.urlopen",side_effect=error) as network,patch("time.sleep"):
                with self.assertRaises(RuntimeError):fetch("https://example.invalid/",out,attempts=2)
            self.assertEqual(network.call_count,2);self.assertFalse(out.exists())
            self.assertTrue(out.with_suffix(".json.error.json").exists())

    def test_changed_provider_schema_fails_loudly(self):
        cross={"data":[{"from":"2025-01-01T00:00Z","intensity":{"actual":55,"forecast":49}}]}
        broken={"success":True,"result":{"renamed_records":[]}}
        with patch("fetch_neso.fetch",side_effect=[(json.dumps(cross).encode(),{}),(json.dumps(broken).encode(),{})]),patch("fetch_neso.record"):
            with self.assertRaisesRegex(ValueError,"schema changed"):
                fetch_neso.ci(2025,"2025-12-31",False)

    def test_offline_sample_coverage_and_digest(self):
        path=ROOT/"data/sample/intervals.json"
        fixture=json.loads(path.read_text(encoding="utf-8"))
        manifest=json.loads((ROOT/"data/manifests/artifacts/gridproof-offline-sample.json").read_text())
        self.assertEqual(sha256(path),manifest["sha256"])
        for day in fixture["metadata"]["dates"]:
            records=[r for r in fixture["intervals"] if r["start_utc"].startswith(day)]
            self.assertEqual(len(records),48);self.assertEqual(profile(records)["gap_count"],0)
            self.assertTrue(all(r["grid_ci_actual_g_per_kwh"] is not None for r in records))
            decision=parse_utc(day+"T00:00:00Z")
            prior=[r for r in fixture["history_intervals"] if decision-timedelta(days=7)<=parse_utc(r["start_utc"])<decision]
            self.assertEqual(len(prior),336)

    def test_fresh_clone_bulk_absence_is_visible_and_missing_sample_fails(self):
        sample=(ROOT/"data/sample/intervals.json").read_bytes()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);man=root/"data/manifests";(man/"artifacts").mkdir(parents=True)
            sample_path=root/"data/sample/intervals.json";sample_path.parent.mkdir(parents=True);sample_path.write_bytes(sample)
            for sid in ["neso-national-ci-2025","neso-demand-2025","openmeteo-london-weather-2025"]:
                (man/"artifacts"/(sid+".json")).write_text(json.dumps({"source_id":sid,"status":"verified","path":"data/raw/absent.json","sha256":"0"*64}))
            (man/"artifacts/gridproof-offline-sample.json").write_text(json.dumps({"source_id":"gridproof-offline-sample","status":"verified","path":"data/sample/intervals.json","sha256":sha256(sample_path)}))
            with patch("validate_sources.ROOT",root),patch("validate_sources.MANIFEST",man),patch("builtins.print"):
                result=validate_sources.validate(False)
                self.assertFalse(result["validation_errors"])
                self.assertTrue(any(c["status"]=="absent_bulk_snapshot" for s in result["sources"] for c in s["local_asset_checks"]))
                with self.assertRaisesRegex(ValueError,"missing data/raw"):
                    validate_sources.validate(True)
                sample_path.unlink()
                with self.assertRaisesRegex(ValueError,"missing data/sample"):
                    validate_sources.validate(False)


if __name__=="__main__":unittest.main()
