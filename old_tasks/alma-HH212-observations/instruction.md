Using the ALMA Science Archive, find all **public, science** observations
targeting the protostar HH 212. Resolve HH 212's coordinates and search by position (not by name string) using a search radius of 1 arcmin. Restrict results to ALMA **Band 6 or 7** observations with an angular resolution **less than one arcsecond**.

Write your findings to `/app/output.json` with this exact schema:

{
  "target_name": "HH 212",
  "resolved_ra_deg": <float>,        // RA used for the positional search
  "resolved_dec_deg": <float>,       // Dec used for the positional search
  "search_radius_arcsec": <float>,   // radius used for the positional search
  "num_observations": <int>,
  "observations": [
    {
      "project_code": "<str>",             // proposal_id
      "alma_source_name": "<str>",         // target_name as recorded in the archive
      "ra_hms": <float>,
      "dec_dms": <float>,
      "band": <int>,                // ALMA band for this observation
      "angular_resolution_arcsec": <float>, // angular resolution 
      "qa2_status": "<str>"                // qa2_passed
    },
    ...
  ],
  "summary": "<3-5 sentence natural-language summary of what's available: how many observations, which bands, resolution range"
}

One row in "observations" per matching archive result. You have internet
access to the ALMA archive ([almascience.org](https://almascience.eso.org/aq/)) and PyPI. `astroquery` and `pyvo` are already installed.