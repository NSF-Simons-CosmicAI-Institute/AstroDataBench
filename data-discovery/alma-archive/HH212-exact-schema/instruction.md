# Summarize ALMA Observations of HH 212

Using the ALMA Science Archive, find all **public, science** observations
targeting the object HH 212, with the following constraints:

- **Band 6 or Band 7** observations only
- **Spatial resolution under 1 arcsecond**, per the ALMA archive's
  `spatial_resolution` column (despite the name, this column actually 
  represents the synthesized beam size in arcsec, not a distance-dependent
  linear/physical resolution)

Instead of searching by name, resolve the coordinates of HH 212 and search by
position with an explicit radius. Note that the archive's TAP/ObsCore interface 
returns one row per spectral window, so a single observation can appear as several 
rows. For this task, "one observation" means one Member Observation Unit Set (MOUS),
which is identified by the `member_ous_uid` column. 

Write your findings to `/app/output.json` with this exact schema:

{
  "target_name": "HH 212",
  "resolved_ra_deg": <float>,        // RA used for the positional search
  "resolved_dec_deg": <float>,       // Dec used for the positional search
  "search_radius_arcsec": <float>,   // radius used for the positional search
  "band_filter": [6, 7],
  "max_spatial_resolution_arcsec": 1.0,
  "num_observations": <int>,         // number of unique member_ous_uid values, AFTER filtering
  "observations": [
    {
      "member_ous_uid": "<str>",            // MOUS grouping key
      "project_code": "<str>",             // proposal_id
      "alma_source_name": "<str>",         // target_name for this observation 
      "ra_deg": <float>,
      "dec_deg": <float>,
      "band": [<int>, ...],              // ALMA band(s) for this observation
      "spatial_resolution_arcsec": <float>, // observation resolution in arcseconds
      "qa2_status": "<str>"                // qa2_passed
    },
    ...
  ],
  "summary": "< 3-5 sentence natural-language summary of what's available: how many observations, which bands, resolution range>"
}

Exactly one row in "observations" per distinct member_ous_uid. You have internet access to the ALMA archive (almascience.org / almascience.nrao.edu / almascience.eso.org) and PyPI. `astroquery`
and `pyvo` are already installed.