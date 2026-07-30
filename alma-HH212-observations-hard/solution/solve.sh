#!/bin/bash
set -euo pipefail

python3 - <<'EOF'
from collections import defaultdict

from astropy.coordinates import SkyCoord
from astropy.time import Time
from astropy import units as u
from astroquery.alma import Alma

SEARCH_RADIUS_ARCSEC = 60.0
BAND_FILTER = ["7"]
MAX_RESOLUTION_ARCSEC = 1.0

alma = Alma()

# Resolve position to avoid issues with target name variations (e.g., HH 212 vs. HH212)
coord = SkyCoord.from_name("HH212")

#Perform query for public observations using the coordinates and search radius
tbl = alma.query_region(
    coord, radius=SEARCH_RADIUS_ARCSEC * u.arcsec,
    band_list=BAND_FILTER, public=True, science=True,
)

# Filter by spatial resolution (in arcseconds, so actually an angular resolution)
tbl = tbl[tbl["spatial_resolution"] < MAX_RESOLUTION_ARCSEC]

# NOTE: ObsCore/TAP returns one row per spectral window, so a single Member OUS
# (MOUS) can appear as several rows. Group by member_ous_uid so each
# physical observation is reported exactly once.
groups = defaultdict(list)
for row in tbl:
    groups[str(row["member_ous_uid"])].append(row)

observations = []

for mous_uid, rows in groups.items():
    resolutions = [float(r["spatial_resolution"]) for r in rows]
    bandwidths = [float(r["bandwidth"]) for r in rows]
    exptimes = [float(r["t_exptime"]) for r in rows]
    obs_date = Time(min(float(r["t_min"]) for r in rows), format="mjd").iso.split(" ")[0]

    observations.append({
        "mous_uid": mous_uid,
        "project_code": rows[0]["proposal_id"],
        "alma_source_name": rows[0]["target_name"],
        "ra_deg": float(rows[0]["s_ra"]),
        "dec_deg": float(rows[0]["s_dec"]),
        "resolution": min(resolutions),
        "bandwidth": sum(bandwidths),
        "exptime": sum(exptimes),
        "date": obs_date,
        "qa2_status": str(rows[0]["qa2_passed"]),
    })

observations.sort(key=lambda o: o["resolution"])

# Create a natural-language write-up, not a JSON file
# ----------------------------------------------------

lines = []
lines.append(f"# HH212 Band 7 Sub-Arcsecond Continuum Data\n")
lines.append(
    f"I searched the ALMA Science Archive around HH212's resolved position "
    f"(RA={coord.ra.deg:.5f}, Dec={coord.dec.deg:.5f}, {SEARCH_RADIUS_ARCSEC}\" "
    f"radius) for public, science-grade Band 7 observations with a synthesized "
    f"beam better than 1 arcsecond. This turned up **{len(observations)} distinct "
    f"observations** (grouped by ALMA Member OUS, since a single observation can "
    f"span multiple spectral windows in the archive).\n"
)

lines.append("## Matching observations\n")
for obs in observations:
    lines.append(
        f"- **{obs['project_code']}** (MOUS `{obs['mous_uid']}`), observed "
        f"{obs['date']}: {obs['resolution']:.3f}\" resolution, "
        f"{obs['bandwidth']:.2f} GHz continuum bandwidth, "
        f"{obs['exptime']:.0f}s integration time."
    )

lines.append("\n## Suitability for a deep, high-resolution continuum image\n")
if observations:
    best = observations[0]
    lines.append(
        f"The {best['project_code']} observation (MOUS `{best['mous_uid']}`) "
        f"has the best resolution at {best['resolution']:.3f}\" and "
        f"{best['bandwidth']:.2f} GHz of continuum bandwidth, making it the "
        f"strongest single candidate for a deep image on its own. "
    )
    if len(observations) > 1:
        lines.append(
            f"Combining visibilities from multiple projects targeting HH212 "
            f"could in principle deepen the image (lower the noise, improve "
            f"uv-coverage), but this requires checking that their array "
            f"configurations, spectral setups, and calibration are compatible "
            f"before concatenating the measurement sets -- projects observed "
            f"at different epochs or with different antenna configurations may "
            f"not combine cleanly without careful re-calibration and "
            f"re-weighting."
        )
else:
    lines.append(
        "No public Band 7 observations meeting the sub-arcsecond resolution "
        "criterion were found for HH212."
    )

with open("/app/answer.md", "w") as f:
    f.write("\n".join(lines))
EOF