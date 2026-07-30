#!/bin/bash
set -euo pipefail

python3 - <<'EOF'
import json
from collections import defaultdict

from astropy.coordinates import SkyCoord
from astropy import units as u
from astroquery.alma import Alma
from dl import queryClient as qc

SEARCH_RADIUS_ARCSEC = 30.0
coord = SkyCoord.from_name("NGC 1068")

# ALMA: no band/resolution filter, since none was requested 
alma = Alma()
tbl = alma.query_region(coord, radius=SEARCH_RADIUS_ARCSEC * u.arcsec, public=True, science=True)

groups = defaultdict(list)
for row in tbl:
    groups[str(row["member_ous_uid"])].append(row)

alma_observations = []
for mous_uid, rows in groups.items():
    bands = sorted({int(b) for r in rows for b in str(r["band_list"]).split()})
    alma_observations.append({
        "member_ous_uid": mous_uid,
        "project_code": rows[0]["proposal_id"],
        "band": bands,
    })

#Data Lab: NOIRLab Source Catalog (NSC) (using dr2 for now)
ra_deg, dec_deg = coord.ra.deg, coord.dec.deg
radius_deg = SEARCH_RADIUS_ARCSEC / 3600.0

nsc_query = f"""
    SELECT COUNT(*) as n FROM nsc_dr2.object
    WHERE q3c_radial_query(ra, dec, {ra_deg}, {dec_deg}, {radius_deg})
"""
nsc_result = qc.query(sql=nsc_query, fmt="pandas")
nsc_n_sources = int(nsc_result["n"].iloc[0])

output = {
    "target": "NGC 1068",
    "ra_deg": ra_deg,
    "dec_deg": dec_deg,
    "alma": {
        "n_observations": len(alma_observations),
        "observations": alma_observations,
    },
    "datalab": {
        "nsc_dr2_n_sources": nsc_n_sources,
        "nsc_dr2_has_coverage": nsc_n_sources > 0,
    },
}

with open("/app/output.json", "w") as f:
    json.dump(output, f, indent=2)
EOF