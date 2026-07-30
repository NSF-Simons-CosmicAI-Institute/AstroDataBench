#!/bin/bash
set -euo pipefail

python3 - <<'EOF'
import json
from collections import defaultdict

from astropy.coordinates import SkyCoord
from astropy import units as u
from astroquery.alma import Alma

SEARCH_RADIUS_ARCSEC = 30.0
MAX_RESOLUTION_ARCSEC = 0.5

alma = Alma()
coord = SkyCoord.from_name("VLA 1623")

tbl = alma.query_region(
    coord, radius=SEARCH_RADIUS_ARCSEC * u.arcsec,
    public=True, science=True,
)
tbl = tbl[tbl["spatial_resolution"] < MAX_RESOLUTION_ARCSEC]

# Proxy for "has continuum data": cont_sensitivity_bandwidth populated.
# NOTE: this is a proxy, not a verified exact match to "continuum product
# available" -- see the HH212 task's continuum-filtering discussion. Worth
# confirming this column name/behavior empirically before trusting fully.
if "cont_sensitivity_bandwidth" in tbl.colnames:
    tbl = tbl[~tbl["cont_sensitivity_bandwidth"].mask] if hasattr(tbl["cont_sensitivity_bandwidth"], "mask") else tbl

groups = defaultdict(list)
for row in tbl:
    groups[str(row["member_ous_uid"])].append(row)

observations = []
for mous_uid, rows in groups.items():
    best_res = min(float(r["spatial_resolution"]) for r in rows)
    bands = sorted({int(b) for r in rows for b in str(r["band_list"]).split()})
    observations.append({
        "member_ous_uid": mous_uid,
        "project_code": rows[0]["proposal_id"],
        "resolution_arcsec": round(best_res, 4),
        "band": bands,
        "qa2": str(rows[0]["qa2_passed"]),
    })

output = {
    "target": "VLA 1623",
    "search": {
        "ra_deg": coord.ra.deg,
        "dec_deg": coord.dec.deg,
        "radius_arcsec": SEARCH_RADIUS_ARCSEC,
    },
    "n_observations": len(observations),
    "observations": observations,
}

with open("/app/output.json", "w") as f:
    json.dump(output, f, indent=2)
EOF