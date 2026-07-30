# stable-benchmark/alma-HH212-observations

**Task:** Resolve the coordinates of HH 212 and use it to perform an ALMA archive query for all public band 6 and 7 data with angular resolution < 1’’. 

**Info. given:** 

- Spatial resolution clarification (the “spatial resolution” column is in arcseconds and actually represents angular resolution)
- Observation definition ****(one MOUS, not one row)
- Output path (`/app/output.json`) and exact schema
- Network access info

**Difficulty**: Easy (single step; task and expected output format are very explicitly defined)

**Verification (test_outputs.py):**

- test_schema: Outputted JSON file has the right fields and structure
- test_row_schema: Right number of observations and non-empty band lists
- test_one_row_per_mous: Exactly one entry per MOUS ID
- test_resolved_position: Coordinate resolved by the agent is within a certain tolerance of the reference position
- test_search_radius: Agent's search radius is within a reasonable range (5-120 arcsec)
- test_declared_filters_match_request: Agent-returned band_filter and max_spatial_resolution_arcsec match the requested values
- test_every_row_matches_band_filter: Every row has at least one band in the allowed/requested band list
- test_every_row_meets_resolution_constraint: Every observation row meets the angular resolution constraint
- test_observation_count_within_tolerance: Number of observations found is within tolerance of the reference number
- test_positions_are_near_target: Every observation row is within SEARCH_RADIUS_ARCSEC of the reference source position.
- test_qa2_status: QA2 status values are within expected options
- test_summary_is_nontrivial: Summary is at least 10 words long