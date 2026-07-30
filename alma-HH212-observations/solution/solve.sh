#!/bin/bash
set -euo pipefail

python3 - <<'EOF'
import json
from collections import defaultdict

import numpy as np
from astropy.coordinates import SkyCoord
from astropy import units as u
from astroquery.alma import Alma

SEARCH_RADIUS_ARCSEC = 60.0 
BAND_FILTER = ["6", "7"]
MAX_RESOLUTION_ARCSEC = 1.0

alma = Alma()

# Resolve position to avoid issues with target name variations (e.g., HH 212 vs. HH212)
coord = SkyCoord.from_name("HH 212")

#Perform query for public observations using the coordinates and search radius
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
observation appears once, not once per spectral window
groups = defaultdict(list)
for row in tbl:
    groups[str(row["member_ous_uid"])].append(row)

observations = []
for mous_uid, rows in groups.items():
    bands = sorted({int(b) for r in rows for b in str(r["band_list"]).split()})
    resolutions = [float(r["spatial_resolution"]) for r in rows]
    observations.append({
        "member_ous_uid": mous_uid,
        "project_code": rows[0]["proposal_id"],
        "alma_source_name": rows[0]["target_name"],
        "ra_deg": float(rows[0]["s_ra"]),
        "dec_deg": float(rows[0]["s_dec"]),
        "band": bands,
        "best_spatial_resolution_arcsec": min(resolutions),
        "qa2_status": str(rows[0]["qa2_passed"]),
    })

all_bands = sorted({b for obs in observations for b in obs["band"]})
all_resolutions = [obs["best_spatial_resolution_arcsec"] for obs in observations]

report = {
    "target_name": "HH 212",
    "resolved_ra_deg": coord.ra.deg,
    "resolved_dec_deg": coord.dec.deg,
    "search_radius_arcsec": SEARCH_RADIUS_ARCSEC,
    "band_filter": [6, 7],
    "max_spatial_resolution_arcsec": MAX_RESOLUTION_ARCSEC,
    "num_observations": len(observations),
    "observations": observations,
    "summary": (
        f"HH 212 has {len(observations)} public ALMA Band 6/7 science "
        f"observations (grouped by Member OUS) with sub-arcsecond spatial "
        f"resolution, covering bands {all_bands}, with resolutions ranging "
        f"from {min(all_resolutions):.3f} to {max(all_resolutions):.3f} arcsec "
        f"across {len(np.unique([o['project_code'] for o in observations]))} "
        f"distinct projects."
    ) if observations else (
        "No public ALMA Band 6/7 science observations with sub-arcsecond "
        "spatial resolution were found for HH 212."
    ),
}

with open("/app/output.json", "w") as f:
    json.dump(report, f, indent=2)
EOF