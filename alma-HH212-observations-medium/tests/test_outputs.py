import json
from collections import defaultdict
from pathlib import Path

import pytest
import re

from astropy.coordinates import SkyCoord
from astropy import units as u
from astroquery.alma import Alma

SEARCH_RADIUS_ARCSEC = 60.0
MAX_RESOLUTION_ARCSEC = 1.0
ALLOWED_BANDS = {6, 7}


def flatten(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from flatten(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from flatten(v, f"{prefix}[{i}]")
    else:
        yield prefix, obj


@pytest.fixture(scope="module")
def agent_output():
    path = Path("/app/output.json")
    assert path.exists(), "Agent did not produce /app/output.json"
    return json.loads(path.read_text())


@pytest.fixture(scope="module")
def flat(agent_output):
    return list(flatten(agent_output))


@pytest.fixture(scope="module")
def reference_coord():
    return SkyCoord.from_name("HH 212")


@pytest.fixture(scope="module")
def reference_groups(reference_coord):
    alma = Alma()
    tbl = alma.query_region(
        reference_coord, radius=SEARCH_RADIUS_ARCSEC * u.arcsec,
        band_list=["6", "7"], public=True, science=True,
    )
    tbl = tbl[tbl["spatial_resolution"] < MAX_RESOLUTION_ARCSEC]
    groups = defaultdict(list)
    for row in tbl:
        groups[str(row["member_ous_uid"])].append(row)
    return groups


def test_output_is_valid_json(agent_output):
    assert isinstance(agent_output, (dict, list))


def _find_observation_arrays(obj, path=""):
    """
    Yield (path, list) for every list of dicts in the structure where the
    dicts look like they represent individual observations
    
    NOTE: This function was written using Claude Sonnet 5, with my comments added"""
    
    OBSERVATION_LIKE_KEYS = {"project", "proposal", "band", "resolution", "uid", "mous"}

    if isinstance(obj, dict):
        #If dict, recursively search its values
        for k, v in obj.items():
            yield from _find_observation_arrays(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        # If list, check if it is a list of dicts...
        if obj and all(isinstance(item, dict) for item in obj):
            sample_keys = " ".join(str(k).lower() for item in obj for k in item.keys())
            # If any of the keys in the dicts match known observation-like keys, yield this list
            if any(term in sample_keys for term in OBSERVATION_LIKE_KEYS):
                yield path, obj
        for i, v in enumerate(obj):
            # Recursively search each item in the list
            yield from _find_observation_arrays(v, f"{path}[{i}]")


def test_observation_count(agent_output, flat, reference_groups):
    expected = len(reference_groups)
    tolerance = max(1, round(0.15 * expected))

    #Level 1:
    #Start by searching for any keys in the output that contain potential observation count identifiers
    potential_identifiers = [
        'obs_count', 'observation_count', 'num_observations',
        'number_of_observations', 'num_obs', 'total_observations',
        'observations_total', 'observations_count', 'obs_total',
        'obs_num', 'obs_number', 'obs_count_total', 'obs_count_num',
        'obs_count_number',
    ]    
    #Check for any keys in the output that contain any of the potential identifiers
    obs_count = [
        value for key, value in flat
        if any(identifier in key.split(".")[-1].split("[")[0].lower() for identifier in potential_identifiers)
    ]
    #Remove any non-integer values from obs_count
    obs_count = [x for x in obs_count if isinstance(x, int) and not isinstance(x, bool)]
    
    if len(obs_count) > 0:
        #If we found any potential observation counts, check if they are within the expected range
        assert any(abs(n - expected) <= tolerance for n in obs_count), (
            f"No reported count near expected {expected} (tolerance {tolerance}) "
            f"found anywhere in the output. Integers present: {sorted(set(obs_count))}"
        )
        return

    # Level 2 (revised): infer count from the structure of an observations-like array
    candidate_arrays = list(_find_observation_arrays(agent_output))
    if candidate_arrays:
        lengths = [len(arr) for _, arr in candidate_arrays]
        assert any(abs(n - expected) <= tolerance for n in lengths), (
            f"No observations-like array with length near {expected} "
            f"(tolerance {tolerance}) found. Array lengths found: {lengths}"
        )
        return

    # If neither level 1 nor level 2 yielded a plausible observation count, fail the test 
    pytest.fail(f"Could not locate any observation count evidence in the output" )


def test_reports_at_least_one_real_project_code(flat, reference_groups):
    """Check at least one of the expected proposal IDs appears
    as a string value somewhere in the output."""
    real_project_codes = {rows[0]["proposal_id"] for rows in reference_groups.values()}
    strings_found = {v for _, v in flat if isinstance(v, str)}
    assert strings_found & real_project_codes, (
        f"None of the real project codes {real_project_codes} appear "
        f"anywhere in the agent's output"
    )

def test_no_hallucinated_project_codes(flat, reference_groups):
    """Check for hallucinated project codes. Any string matching the
    ALMA proposal-ID pattern (YYYY.N.NNNNN.S) should be a real one"""
    real_project_codes = {rows[0]["proposal_id"] for rows in reference_groups.values()}
    proposal_pattern = re.compile(r"^\d{4}\.\d\.\d{5}\.[SA]$")
    for _, v in flat:
        if isinstance(v, str) and proposal_pattern.match(v):
            assert v in real_project_codes, f"Reported project code {v} not found in a fresh archive query"


def test_reported_resolutions(flat):
    """Any key that looks like it corresponds to a resolution/beam size field
    should hold a value under the stated threshold. Searches for substrings to allow
    for some name variation"""
    resolution_like_keys = [
        (k, v) for k, v in flat
        if isinstance(v, (int, float))
        and any(term in k.lower() for term in ["resolution", "beam"])
        #exclude keys that appear to correspond to spectral resolution
        and not any(exclude in k.lower() for exclude in ["spectral", "frequency", "freq", "velocity", "vel"])
    ]
    assert resolution_like_keys, "No resolution/beam-size value identified anywhere in the output"
    for k, v in resolution_like_keys:
        assert 0 < v < MAX_RESOLUTION_ARCSEC + 1e-6, (
            f"Field '{k}' = {v} violates the {MAX_RESOLUTION_ARCSEC} arcsec constraint"
        )


def test_reported_bands(flat):
    """Any integer that looks like an ALMA band number (values 1-10) should
    be in the allowed set, if reported under a band-like key."""
    band_like = [
        (k, v) for k, v in flat 
        if "band" in k.lower() and "bandwidth" not in k.lower()
    ]
    assert band_like, "No band-related field found anywhere in the output"
    for k, v in band_like:
        #Turn into a list if it isn't already one
        values = v if isinstance(v, list) else [v]
        # Check if these values follow the requested band constraint
        for item in values:
            if isinstance(item, int) and 1 <= item <= 10:
                assert item in ALLOWED_BANDS, f"Field '{k}' reports band {item}, not in {ALLOWED_BANDS}"


