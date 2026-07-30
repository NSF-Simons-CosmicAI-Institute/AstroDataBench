import json
from collections import defaultdict
from pathlib import Path

import pytest
from astropy.coordinates import SkyCoord
from astropy import units as u
from astroquery.alma import Alma

SEARCH_RADIUS_ARCSEC = 60.0
MAX_RESOLUTION_ARCSEC = 1.0
BANDS = [6,7]


def flatten(obj, prefix=""):
    """Flattens a dictionary or list into a list of key-value pairs"""
    results = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            results.extend(flatten(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            results.extend(flatten(v, f"{prefix}[{i}]"))
    else:
        results.append((prefix, obj))
    return results

@pytest.fixture(scope="module")
def agent_output():
    """" Fixture to load the agent's output.json file (which should have been produced
    in /app/output.json)
    """
    path = Path("/app/output.json")
    assert path.exists(), "Agent did not produce /app/output.json"
    return json.loads(path.read_text())

@pytest.fixture(scope="module")
def flat(agent_output):
    """ Fixture to flatten the agent's output.json file into a list of key-value pairs
    """
    return list(flatten(agent_output))


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

def test_output_is_valid_json(agent_output):
    """
    Test that the agent's output.json file is valid JSON (the agent_output fixture will raise an error if the file isn't)
    """
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