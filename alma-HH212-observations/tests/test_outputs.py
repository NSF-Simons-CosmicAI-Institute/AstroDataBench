"""
Harbor template notes:
Use this file to define pytest tests that verify the outputs of the task.

This file will be copied to /tests/test_outputs.py and run by the /tests/test.sh file
from the working directory.
"""

import json
from collections import defaultdict
from pathlib import Path

import pytest
from astropy.coordinates import SkyCoord
from astropy import units as u
from astroquery.alma import Alma

#Define constants for the tests

REQUIRED_ROW_FIELDS = [
    "member_ous_uid", "project_code", "alma_source_name", "ra_deg", "dec_deg",
    "band", "best_spatial_resolution_arcsec", "qa2_status",
]

REQUIRED_TOP_LEVEL_FIELDS = [
    "target_name", "resolved_ra_deg", "resolved_dec_deg",
    "search_radius_arcsec", "band_filter", "max_spatial_resolution_arcsec",
    "num_observations", "observations", "summary",
]

RESOLVER_TOLERANCE_ARCSEC = 5.0
ALLOWED_BANDS = {6, 7}
MAX_RESOLUTION_ARCSEC = 1.0
SEARCH_RADIUS_ARCSEC = 60.0
BANDS = ["6", "7"]


@pytest.fixture(scope="module")
def agent_output():
    """" Fixture to load the agent's output.json file (which should have been produced
    in /app/output.json)
    """
    
    path = Path("/app/output.json")
    assert path.exists(), "Agent did not produce /app/output.json"
    return json.loads(path.read_text())


@pytest.fixture(scope="module")
def reference_coord():
    """ Fixture to provide a reference SkyCoord for HH 212, used in multiple 
    tests"""
    
    return SkyCoord.from_name("HH 212")


@pytest.fixture(scope="module")
def reference_groups(reference_coord):
    """Achive query grouped by member_ous_uid. Uses the same defintion of "observation"
      as the agent so that the number of observations can be compared
    """

    alma = Alma()
    tbl = alma.query_region(
        reference_coord, radius=SEARCH_RADIUS_ARCSEC * u.arcsec,
        band_list=BANDS, public=True, science=True,
    )
    tbl = tbl[tbl["spatial_resolution"] < MAX_RESOLUTION_ARCSEC]

    groups = defaultdict(list)
    for row in tbl:
        groups[str(row["member_ous_uid"])].append(row)
    return groups

def test_schema(agent_output):
    """"Check if the agent's output JSON has the required top-level fields and that
    "observations" is a list
    """

    for key in REQUIRED_TOP_LEVEL_FIELDS:
        assert key in agent_output, f"Missing top-level key: {key}"
    assert isinstance(agent_output["observations"], list)


def test_row_schema(agent_output):
    """Check the number of observations and if each observation row has the required 
    fields and that "band" is a non-empty list
    """

    assert len(agent_output["observations"]) == agent_output["num_observations"]
    for row in agent_output["observations"]:
        for field in REQUIRED_ROW_FIELDS:
            assert field in row, f"Missing field '{field}' in observation row"
        assert isinstance(row["band"], list) and len(row["band"]) > 0

#
def test_one_row_per_mous(agent_output):
    """Check that there's exactly one entry per member_ous_uid
    (no duplicates from un-grouped spectral-window rows)
    """

    uids = [row["member_ous_uid"] for row in agent_output["observations"]]
    assert len(uids) == len(set(uids)), (
        "Duplicate member_ous_uid values found; observations should be "
        "grouped by MOUS, not left as raw per-spectral-window rows"
    )


def test_resolved_position(agent_output, reference_coord):

    """Check that the agent-returned position is within RESOLVER_TOLERANCE_ARCSEC of 
    the reference HH 212 position
    """

    agent_pos = SkyCoord(
        ra=agent_output["resolved_ra_deg"] * u.deg,
        dec=agent_output["resolved_dec_deg"] * u.deg,
    )
    sep = reference_coord.separation(agent_pos).arcsec
    assert sep <= RESOLVER_TOLERANCE_ARCSEC, (
        f"Resolved position is {sep:.2f}\" from a fresh HH 212 resolution "
        f"(tolerance {RESOLVER_TOLERANCE_ARCSEC}\"). Source is likely not properly resolved"
    )


def test_search_radius(agent_output):
    """Check that the agent's search radius is within a reasonable range (5-120 arcsec)"""

    radius = agent_output["search_radius_arcsec"]
    assert 5.0 <= radius <= 120.0, (
        f"search_radius_arcsec={radius} is outside a reasonable range"
    )


def test_declared_filters_match_request(agent_output):
    """Check that the agent-returned band_filter and max_spatial_resolution_arcsec
    match the requested values (ALLOWED_BANDS and MAX_RESOLUTION_ARCSEC)"""

    assert set(agent_output["band_filter"]) == ALLOWED_BANDS, (
        f"band_filter should be [6, 7], got {agent_output['band_filter']}"
    )
    assert agent_output["max_spatial_resolution_arcsec"] == MAX_RESOLUTION_ARCSEC


def test_every_row_matches_band_filter(agent_output):
    """Check that every observation row has at least one band in ALLOWED_BANDS
    """
    for row in agent_output["observations"]:
        #Check if there's overlap between the reported bands and the allowed bands
        assert set(row["band"]) & ALLOWED_BANDS, (
            f"Row for {row['alma_source_name']} has band(s) {row['band']}, "
            f"none of which are in {ALLOWED_BANDS}"
        )


def test_every_row_meets_resolution_constraint(agent_output):
    """Check that every observation row has best_spatial_resolution_arcsec < MAX_RESOLUTION_ARCSEC
    """

    for row in agent_output["observations"]:
        res = row["best_spatial_resolution_arcsec"]
        assert 0 < res < MAX_RESOLUTION_ARCSEC, (
            f"Row for {row['alma_source_name']} has best_spatial_resolution_arcsec="
            f"{res}, which violates the <{MAX_RESOLUTION_ARCSEC} arcsec constraint"
        )


def test_observation_count_within_tolerance(agent_output, reference_groups):
    """Tight tolerance because the MOUS grouping definition
    is defined and required in the task instructions
    """

    expected = len(reference_groups)
    got = agent_output["num_observations"]
    assert abs(got - expected) <= 1, (
        f"Expected {expected} MOUS-grouped observations near HH 212, "
        f"agent reported {got}"
    )


def test_positions_are_near_target(agent_output, reference_coord):
    """Check that every observation row is within SEARCH_RADIUS_ARCSEC of the reference
    source position. Allow a small tolerance of 5 arcsec to account for any
    differences in the resolved position and the reference position.
    """

    for row in agent_output["observations"]:
        pos = SkyCoord(ra=row["ra_deg"] * u.deg, dec=row["dec_deg"] * u.deg)
        sep = reference_coord.separation(pos).arcsec
        assert sep < SEARCH_RADIUS_ARCSEC + 5, (
            f"Row for {row['alma_source_name']} is {sep:.1f}\" from HH 212 "
            "-- likely the wrong source"
        )


def test_qa2_status(agent_output, reference_groups):
    """Check that every observation row has a qa2_status value that is in the set of observations
    in the reference query"""

    ref_values = {
        str(r["qa2_passed"]) for rows in reference_groups.values() for r in rows
    }
    for row in agent_output["observations"]:
        assert row["qa2_status"] in ref_values, (
            f"Unexpected qa2_status value: {row['qa2_status']!r}"
        )


def test_summary_is_nontrivial(agent_output):
    """Check that the agent's summary is at least 10 words long, to avoid trivial summaries
    """
    
    assert len(agent_output["summary"].split()) >= 10
