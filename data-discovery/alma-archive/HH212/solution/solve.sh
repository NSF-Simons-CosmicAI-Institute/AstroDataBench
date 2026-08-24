#!/bin/bash
set -euo pipefail

python3 - <<'EOF'
import json
from collections import defaultdict

from astropy.coordinates import SkyCoord
from astropy import units as u
from astroquery.alma import Alma

SEARCH_RADIUS_ARCSEC = 60.0
BAND_FILTER = ["6", "7"]
MAX_RESOLUTION_ARCSEC = 1.0

alma = Alma()

# Resolve position to avoid issues with target name variations (e.g., HH 212 vs. HH212)
coord = SkyCoord.from_name("HH 212")

tbl = alma.query_region(
    coord,
    radius=SEARCH_RADIUS_ARCSEC * u.arcsec,
    band_list=BAND_FILTER,
    public=True,
    science=True,
)

# Filter by spatial resolution (in arcseconds, so actually an angular resolution)
tbl = tbl[tbl["spatial_resolution"] < MAX_RESOLUTION_ARCSEC]

# NOTE: ObsCore/TAP returns one row per spectral window, so a single Member OUS
# (MOUS) can appear as several rows. Group by member_ous_uid so each physical 
#observation appears once, not once per spectral window
groups = defaultdict(list)
for row in tbl:
    groups[str(row["member_ous_uid"])].append(row)


# NOTE: The field names here are different from the stricter version of this task
# to check that the grading allows reasonable naming variations rather
# than exact matches
results = []
for mous_id, rows in groups.items():
    bands = sorted({int(b) for r in rows for b in str(r["band_list"]).split()})
    best_resolution = min(float(r["spatial_resolution"]) for r in rows)
    results.append({
        "mous_id": mous_id,
        "project_code": rows[0]["proposal_id"],
        "source_name": rows[0]["target_name"],
        "resolution_arcsec": round(best_resolution, 4),
        "band": bands,
        "qa2": str(rows[0]["qa2_passed"]),
    })

output = {
    "target": "HH 212",
    "search": {
        "ra_deg": coord.ra.deg,
        "dec_deg": coord.dec.deg,
        "radius_arcsec": SEARCH_RADIUS_ARCSEC,
    },
    "n_observations": len(results),
    "observations": results,
}

with open("/app/output.json", "w") as f:
    json.dump(output, f, indent=2)
EOF