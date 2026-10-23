"""Fetch real workplace EV charging sessions (a.s.r. office parking lot, Utrecht).

Source: de Bont et al. (2025), "Electric Vehicle Charging Session Data of Large
Office Parking Lot", 4TU.ResearchData, version 2,
doi:10.4121/80ef3824-3f5d-4e45-8794-3b8791efbd13.v2. Licence CC BY-NC-SA 4.0.
Used here for non-commercial research only; derived session statistics remain
under the same licence and attribution. No account or token is required.
"""
from __future__ import annotations
import hashlib
from acquisition import RAW, fetch, record, relative

BASE = "https://data.4tu.nl/file/80ef3824-3f5d-4e45-8794-3b8791efbd13/"
FILES = {
    "README.txt": ("f2dbd7cf-0647-45c5-8e44-ab3b6d35ad6a", "382fab9d855e7a3e29c55c6b0e8ce3e8"),
    "202410DatasetEVOfficeParking_v0.csv": ("f2e3498b-1f30-45ac-a440-25215e83f94d", "1c3eef11775c274c239c77714ad0705a"),
}
OUT = RAW / "workplace_sessions_utrecht"


def main():
    artifacts = []
    for name, (file_id, md5) in FILES.items():
        body, meta = fetch(BASE + file_id, OUT / name, timeout=90)
        actual = hashlib.md5(body).hexdigest()
        if actual != md5:
            raise ValueError(f"{name}: MD5 {actual} differs from repository-published {md5}")
        artifacts.append({"path": relative(OUT / name), "sha256": meta["sha256"], "md5_published": md5,
                          "byte_size": meta["byte_size"], "fetched_utc": meta["fetched_utc"]})
    record("utrecht-workplace-ev-sessions",
           title="Electric Vehicle Charging Session Data of Large Office Parking Lot (v2)",
           doi="10.4121/80ef3824-3f5d-4e45-8794-3b8791efbd13.v2", licence="CC BY-NC-SA 4.0",
           publisher="4TU.ResearchData / University of Twente", coverage="2020-08-25 to 2024-10-02, Utrecht NL",
           use="Driver arrival, dwell and energy behaviour only; combined with GB grid records as a constructed scenario",
           artifacts=artifacts)
    print("OK", [a["path"] for a in artifacts])


if __name__ == "__main__":
    main()
