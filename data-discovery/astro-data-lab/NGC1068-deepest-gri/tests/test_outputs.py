import json
from pathlib import Path
import collections

import numpy as np
import pytest

from astropy.coordinates import SkyCoord
from astropy import units as u
from pyvo.dal import sia

DEF_ACCESS_URL = (
    "https://datalab.noirlab.edu/sia/nsa"  # general NOIRLab Science Archive
)
svc = sia.SIAService(DEF_ACCESS_URL)

NAME = "NGC 1068"
COORD = SkyCoord.from_name(NAME)
RA_DEG, DEC_DEG = COORD.ra.deg, COORD.dec.deg
TARGET_BANDS = ["g", "r", "i"]
EXPTIME_TOLERANCE_SEC = 5  # Allowable difference in exposure time (seconds) between reference and agent output


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
def reference_images():
    """Retrieve the reference stacked images for NGC 1068 from the NOIRLab Science Archive SIA service"""
    svc = sia.SIAService(DEF_ACCESS_URL)
    fov = 0.1
    # Retrieve cutout info
    result = svc.search(
        (RA_DEG, DEC_DEG),
        (fov / np.cos(DEC_DEG * np.pi / 180), fov),
    )
    tbl = result.to_table()
    # Return only the stacked images
    return tbl[(tbl["prodtype"] == "image") & (tbl["proctype"] == "Stack")]


@pytest.fixture(scope="module")
def deepest_images(reference_images):
    """Retrieve the deepest stacked images for each band from the reference science stacks"""
    deepest = {}
    # Iterate through each target band and find the deepest stack (max exposure time) for that band
    for band in TARGET_BANDS:
        band_rows = reference_images[reference_images["obs_bandpass"] == band]
        if len(band_rows) == 0:
            deepest[band] = None
            continue
        # Find the row corresponding to the deepest stack for this band
        deepest_idx = np.argmax(band_rows["exptime"])
        deepest_row = band_rows[deepest_idx]
        deepest[band] = {
            "access_url": str(deepest_row["access_url"]),
            "exptime_sec": float(deepest_row["exptime"]),
        }
    return deepest


@pytest.fixture(scope="module")
def reported_bands(flat):
    """Look for band-like key, value pairs"""
    band_like_keys = [k for k, v in flat if "band" in k.lower()]
    bands = [v.lower() for k, v in flat if "band" in k.lower()]
    yield bands


@pytest.fixture(scope="module")
def reported_urls(flat):
    """Look for url-like key, value pairs"""
    url_like_keys = [k for k, v in flat if "url" in k.lower()]
    urls = [v for k, v in flat if "url" in k.lower()]
    return urls


@pytest.fixture(scope="module")
def reported_exptimes(flat):
    """Look for exposure time-like key, value pairs"""
    potential_identifiers = ["exptime", "time", "t_exp", "exp_time", "exposure"]
    exptime_like_keys = [
        k
        for k, v in flat
        if any(identifier in k.lower() for identifier in potential_identifiers)
    ]
    exptimes = [
        v
        for k, v in flat
        if any(identifier in k.lower() for identifier in potential_identifiers)
    ]
    return exptimes


def test_valid_json(agent_output):
    """Check that the agent's output is valid JSON"""
    assert isinstance(agent_output, (dict, list)), "Agent output is not valid JSON"


def test_correct_bandlist(reported_bands):
    """Check that the list of bands reported exactly matches the target bands"""
    # Check to see if the correct number of bands are reported
    assert len(reported_bands) == len(
        TARGET_BANDS
    ), f"Number of bands reported {len(reported_bands)} does not match the number of target bands {len(TARGET_BANDS)}"
    # Then check that the reported bands match the target bands
    assert collections.Counter(reported_bands) == collections.Counter(
        TARGET_BANDS
    ), f"Reported band list '{reported_bands}' does not match target band list {TARGET_BANDS}"


@pytest.mark.parametrize("band", TARGET_BANDS)
def test_correct_urls(band, reported_bands, reported_urls, deepest_images):
    """Check that for each target band, the deepest stacked image's access URL is present"""
    assert band in reported_bands, f"Band {band} was not reported"
    reference_url = deepest_images[band]["access_url"]
    assert (
        reference_url in reported_urls
    ), f"Band {band}: URL of the deepest stacked image incorrect or not reported"


@pytest.mark.parametrize("band", TARGET_BANDS)
def test_correct_exptimes(band, reported_bands, reported_exptimes, deepest_images):
    """Check that for each target band, the deepest stacked image's exposure time is present"""
    assert band in reported_bands, f"Band {band} was not reported"
    reported_exptimes_float = [
        float("".join([i for i in time if i.isnumeric() or i == "."]))
        for time in reported_exptimes
    ]
    reference_exptime = float(deepest_images[band]["exptime_sec"])
    assert (
        reference_exptime in reported_exptimes_float
    ), f"Band {band}: Exposure time of the deepest stacked image incorrect or not reported"


# import json
# from pathlib import Path


# import numpy as np
# import pytest
# from pyvo.dal import sia

# from astropy.coordinates import SkyCoord
# from astropy import units as u
# from pyvo.dal import sia

# DEF_ACCESS_URL = "https://datalab.noirlab.edu/sia/nsa"  # general NOIRLab Science Archive
# svc = sia.SIAService(DEF_ACCESS_URL)

# NAME = "NGC 1068"
# COORD = SkyCoord.from_name(NAME)
# RA_DEG, DEC_DEG = COORD.ra.deg, COORD.dec.deg
# TARGET_BANDS = ["g", "r", "i"]
# EXPTIME_TOLERANCE_SEC = 5  # Allowable difference in exposure time (seconds) between reference and agent output

# def flatten(obj, prefix=""):
#     if isinstance(obj, dict):
#         for k, v in obj.items():
#             yield from flatten(v, f"{prefix}.{k}" if prefix else k)
#     elif isinstance(obj, list):
#         for i, v in enumerate(obj):
#             yield from flatten(v, f"{prefix}[{i}]")
#     else:
#         yield prefix, obj

# @pytest.fixture(scope="module")
# def agent_output():
#     path = Path("/app/output.json")
#     assert path.exists(), "Agent did not produce /app/output.json"
#     return json.loads(path.read_text())


# @pytest.fixture(scope="module")
# def flat(agent_output):
#     return list(flatten(agent_output))

# @pytest.fixture(scope="module")
# def reference_science_stacks():
#     svc = sia.SIAService(DEF_ACCESS_URL)
#     fov = 0.1
#     result = svc.search(
#         (RA_DEG, DEC_DEG),
#         (fov / np.cos(DEC_DEG * np.pi / 180), fov),
#     )
#     tbl = result.to_table()
#     return tbl[
#         (tbl["prodtype"] == "image") &
#         (tbl["proctype"] == "Stack")
#     ]

# @pytest.fixture(scope="module")
# def reference_deepest_per_band(reference_science_stacks):
#     deepest = {}
#     for band in TARGET_BANDS:
#         band_rows = reference_science_stacks[reference_science_stacks["obs_bandpass"] == band]
#         if len(band_rows) == 0:
#             deepest[band] = None
#             continue
#         idx = np.argmax(band_rows["exptime"])
#         row = band_rows[idx]
#         deepest[band] = {
#             "access_url": str(row["access_url"]),
#             "exptime_sec": float(row["exptime"]),
#         }
#     return deepest

# def test_output_is_valid_json(agent_output):
#     assert isinstance(agent_output, (dict, list))

# def test_reference_data_is_available(reference_deepest_per_band):
#     """Check that the reference data is available for all target bands."""
#     missing = [b for b, v in reference_deepest_per_band.items() if v is None]
#     assert not missing, (
#         f"No stacked science images found for band(s) {missing}; please verify "
#         f"obs_bandpass values and stack availability before grading against this task"
#     )

# # def test_output_length(agent_output):
# #     assert len(agent_output) == len(TARGET_BANDS), (
# #         f"Output should contain {len(TARGET_BANDS)} images, one for each target band"
# #     )

# def test_output_bands(agent_output, flat):
#     band_like_keys = [
#         (k, v) for k, v in flat
#         if "band" in k.lower()
#     ]
#     assert band_like_keys, "No band-related field found anywhere in the output"
#     for k, v in band_like_keys:
#         #Turn into a list if it isn't already one
#         values = v if isinstance(v, list) else [v]
#         # Check if these values follow the requested band constraint
#         for item in values:
#             if isinstance(item, str):
#                 assert item in TARGET_BANDS, f"Field '{k}' reports band {item}, not in {TARGET_BANDS}"
#             else:
#                 pytest.fail(f"Field '{k}' reports non-string value {item} (type {type(item)})")


# def test_reports_correct_urls():
#     """For each band, check that the true deepest image's access_url
#     appears in the output"""
#     band_like_keys = [(k, v) for k, v in flat if "band" in k.lower()]
#     for i, (k, v) in enumerate(band_like_keys):
#         ref = reference_deepest_per_band[v]
#         ref_url = ref["access_url"]
#         ref_exptime = ref["exptime_sec"]
#         assert ref_url in str(flat), f"Band {v} does not report the deepest image's access_url {ref_url}"

# def test_reports_correct_urls():
#     """For each band, check that the true deepest image's access_url
#     appears in the output"""
#     band_like_keys = [(k, v) for k, v in flat if "band" in k.lower()]
#     for i, (k, v) in enumerate(band_like_keys):
#         ref = reference_deepest_per_band[v]
#         ref_url = ref["access_url"]
#         ref_exptime = ref["exptime_sec"]
#         assert ref_url in str(flat), f"Band {v} does not report the deepest image's access_url {ref_url}"

# def test_no_fabricated_access_urls(flat, reference_science_stacks):
#     """Any string that looks like a Data Lab access URL should correspond
#     to a real row from a fresh query, not a hallucinated one."""
#     real_urls = set(str(u) for u in reference_science_stacks["access_url"])
#     for _, v in flat:
#         if isinstance(v, str) and "datalab.noirlab.edu" in v and 'cutout' in v:
#             assert v in real_urls, f"Reported access_url {v} not found in a fresh archive query"

# # def test_reports_correct_deepest_image_per_band(flat, reference_deepest_per_band):
# #     """For each band, check that either the true deepest image's access_url
# #     appears in the output, or a reported exposure time is within tolerance
# #     of the true maximum. Accommodates near-ties and agent-chosen field
# #     naming."""
# #     for band in TARGET_BANDS:
# #         ref = reference_deepest_per_band[band]
# #         if ref is None:
# #             continue
# #         ref_url = ref["access_url"]
# #         ref_exptime = ref["exptime_sec"]
# #         # Find all reported access_urls and exposure times for this band
# #         reported_urls = [
# #              for k, v in flat
# #             if "band" in k.lower() and str(v).lower() == band.lower()
# #         ]
