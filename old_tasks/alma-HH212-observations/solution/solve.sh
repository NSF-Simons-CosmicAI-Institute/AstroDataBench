#!/bin/bash
set -euo pipefail

python3 - <<'EOF'
import json
from astroquery.alma import Alma
import astropy.coordinates

alma = Alma()

coordinates = astropy.coordinates.SkyCoord.from_name("HH 212")
tbl = alma.query_region(coordinates, public=True, science=True)
bands = sorted({int(b) for row in tbl["band_list"] for b in str(row).split()})
proposals = sorted(set(tbl["proposal_id"]))
earliest = min(tbl["t_min"])  # MJD

from astropy.time import Time
earliest_iso = Time(earliest, format="mjd").iso.split(" ")[0]

report = {
    "target_name": "M83",
    "num_observations": len(tbl),
    "bands_observed": bands,
    "proposal_ids": proposals,
    "earliest_obs_date": earliest_iso,
    "summary": f"M83 has {len(tbl)} public ALMA science observations across "
               f"bands {bands}, spanning {len(proposals)} proposals since {earliest_iso}.",
}

with open("/app/output.json", "w") as f:
    json.dump(report, f, indent=2)
EOF