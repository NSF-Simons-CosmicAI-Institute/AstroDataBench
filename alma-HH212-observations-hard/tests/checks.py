"""
Programmatic Reward Kit criteria. Each @criterion function receives the
agent's workspace and returns a bool or float. These compute ground truth
fresh from the archive (same pattern used throughout this task's
development) and then look for evidence of that ground truth inside the
agent's free-form answer.md, rather than requiring a fixed schema.
"""

import re
from collections import defaultdict
from pathlib import Path

from astropy.coordinates import SkyCoord
from astropy import units as u
from astroquery.alma import Alma
from rewardkit import criterion

SEARCH_RADIUS_ARCSEC = 60.0
MAX_RESOLUTION_ARCSEC = 1.0


def _fresh_ground_truth():
    """Re-query the archive live, same methodology as solve.sh."""
    coord = SkyCoord.from_name("HH212")
    alma = Alma()
    tbl = alma.query_region(
        coord, radius=SEARCH_RADIUS_ARCSEC * u.arcsec,
        band_list=["7"], public=True, science=True,
    )
    tbl = tbl[tbl["spatial_resolution"] < MAX_RESOLUTION_ARCSEC]

    groups = defaultdict(list)
    for row in tbl:
        groups[str(row["member_ous_uid"])].append(row)

    return {
        "coord": coord,
        "num_observations": len(groups),
        "project_codes": {rows[0]["proposal_id"] for rows in groups.values()},
        "best_resolution": min(
            float(r["spatial_resolution"]) for rows in groups.values() for r in rows
        ) if groups else None,
    }


@criterion
def answer_file_exists(workspace: Path) -> bool:
    return (workspace / "answer.md").exists()


@criterion
def reports_plausible_observation_count(workspace: Path) -> float:
    """Loose, tolerance-based check: does *some* number in the answer land
    near the true MOUS count? Wide tolerance since the agent may reasonably
    choose a different search radius or grouping approach than solve.sh."""
    path = workspace / "answer.md"
    if not path.exists():
        return 0.0
    text = path.read_text()
    expected = _fresh_ground_truth()["num_observations"]
    if expected == 0:
        return 1.0  # nothing to match against

    tolerance = max(3, round(0.25 * expected))
    numbers_found = [int(n) for n in re.findall(r"\b\d+\b", text)]
    return 1.0 if any(abs(n - expected) <= tolerance for n in numbers_found) else 0.0


@criterion
def mentions_at_least_one_real_project_code(workspace: Path) -> float:
    """Checks the answer references at least one project code that actually
    exists in a fresh archive query -- catches fabricated/hallucinated
    project IDs, independent of exact count or formatting."""
    path = workspace / "answer.md"
    if not path.exists():
        return 0.0
    text = path.read_text()
    truth = _fresh_ground_truth()
    if not truth["project_codes"]:
        return 1.0
    return 1.0 if any(code in text for code in truth["project_codes"]) else 0.0


@criterion
def resolution_values_are_plausible(workspace: Path) -> float:
    """Any arcsec-labeled number claimed in the answer should be under the
    1 arcsec threshold the user asked for -- catches an agent that reports
    resolution values that don't actually satisfy the stated constraint."""
    path = workspace / "answer.md"
    if not path.exists():
        return 0.0
    text = path.read_text()
    arcsec_values = [
        float(m) for m in re.findall(r'(\d+\.?\d*)\s*(?:arcsec|")', text)
    ]
    if not arcsec_values:
        return 0.0  # answer never actually cited a resolution figure
    return 1.0 if all(v < 1.5 for v in arcsec_values) else 0.0
    # NOTE: 1.5 rather than 1.0 as a loose ceiling, since some cited
    # resolution values in a real answer might reasonably refer to a
    # *requested* array configuration spec rather than an achieved value.
    # This heuristic is a first draft -- verify it doesn't false-fail on
    # your own solve.sh output before trusting it.