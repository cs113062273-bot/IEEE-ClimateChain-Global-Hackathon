"""Generate inspectable diagnostic charts from local data, without fetching anything."""
import json
import argparse
from pathlib import Path
from acquisition import *


def storage():
    import duckdb
    db_path=PROCESSED/"gridproof.duckdb"
    con=duckdb.connect(str(db_path))
    con.execute("SET TimeZone='UTC'")
    assets=[]
    tables={}
    try:
        for name in ["neso_ci_2025","neso_ci_2026","neso_demand_2025","weather_2025","intervals_2025"]:
            source=PROCESSED/(name+".csv")
            if not source.exists():continue
            con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM read_csv(?, header=true, sample_size=-1, types={{'start_utc':'TIMESTAMPTZ','end_utc':'TIMESTAMPTZ'}})",[str(source)])
            rows=con.execute(f"SELECT count(*),count(DISTINCT start_utc),min(start_utc),max(end_utc) FROM {name}").fetchone()
            if rows[0]!=rows[1]:raise ValueError(f"Duplicate storage timestamps: {name}")
            out=PROCESSED/(name+".parquet")
            literal=str(out).replace("'","''")
            con.execute(f"COPY {name} TO '{literal}' (FORMAT PARQUET, COMPRESSION ZSTD)")
            tables[name]={"rows":rows[0],"coverage_start_utc":utc_text(rows[2]),"coverage_end_utc_exclusive":utc_text(rows[3]),"schema":[{"column":x[0],"type":x[1]} for x in con.execute(f"DESCRIBE {name}").fetchall()]}
            assets.append({"path":relative(out),"sha256":sha256(out),"byte_size":out.stat().st_size,"lineage_csv":relative(source),"lineage_csv_sha256":sha256(source),"row_count":rows[0]})
        con.execute("CHECKPOINT")
    finally:
        con.close()
    assets.append({"path":relative(db_path),"sha256":sha256(db_path),"byte_size":db_path.stat().st_size})
    record("gridproof-columnar-storage",status="verified",license="Upstream source licences apply",attribution="Supported by National Energy SO Open Data; Open-Meteo / ECMWF ERA5",original_url=None,
           fetched_utc=now_utc(),provenance_status="normalized_authentic_grid_estimates_and_weather_reanalysis",storage_artifacts=assets,tables=tables,
           path=relative(db_path),sha256=sha256(db_path),byte_size=db_path.stat().st_size,row_count=sum(t["rows"] for t in tables.values()),content_type="application/vnd.duckdb",http_status=None,etag=None,
           timezone="UTC",units="Inherited from normalized CSV/source manifest",transformations=["Typed UTC TIMESTAMPTZ interval endpoints", "DuckDB tables and ZSTD Parquet from unchanged normalized CSV values"],
           limitations=["Bulk files not distributed with source code", "Database digest depends on storage serialization, not just logical values"],duckdb_version=duckdb.__version__)
    print(f"STORAGE {len(tables)} DuckDB tables and ZSTD Parquet snapshots")


def plot():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fixture=json.loads((ROOT/"data/sample/intervals.json").read_text(encoding="utf-8"))
    fig,axes=plt.subplots(2,2,figsize=(12,6),constrained_layout=True)
    for column,day in enumerate(fixture["metadata"]["dates"]):
        rows=[r for r in fixture["intervals"] if r["start_utc"].startswith(day)]
        x=[parse_utc(r["start_utc"]).hour+parse_utc(r["start_utc"]).minute/60 for r in rows]
        axes[0,column].plot(x,[r["grid_ci_actual_g_per_kwh"] for r in rows],label="NESO actual estimate")
        axes[0,column].plot(x,[r["grid_ci_forecast_g_per_kwh"] for r in rows],label="Historic forecast (issue time unknown)",linestyle="--")
        axes[0,column].set(title=day,ylabel="gCO2/kWh",xlim=(0,24));axes[0,column].legend(fontsize=8)
        axes[1,column].step(x,[r["shortwave_radiation_w_per_m2"] for r in rows],where="post",label="ERA5 hourly mean split to 30m",color="#dd8b22")
        axes[1,column].set(ylabel="Shortwave radiation W/m²",xlabel="UTC hour",xlim=(0,24));axes[1,column].legend(fontsize=8)
    fig.suptitle("GridProof source QA: authentic GB grid estimates and London weather reanalysis")
    out=ROOT/"docs/assets/data_quality.png";out.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(out,dpi=140);plt.close(fig)
    print(f"DIAGNOSTIC {out.relative_to(ROOT)}")


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--plot-only",action="store_true");args=p.parse_args()
    if not args.plot_only:storage()
    plot()
