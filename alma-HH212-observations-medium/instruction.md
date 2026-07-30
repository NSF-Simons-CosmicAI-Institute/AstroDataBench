# Summarize ALMA Observations of HH 212

Using the ALMA Science Archive, find all **public, science** observations
targeting the object HH 212, with the following constraints:

- **Band 6 or Band 7** observations only
- **Spatial resolution under 1 arcsecond**, per the ALMA archive's
  `spatial_resolution` column (despite the name, this column actually 
  represents the synthesized beam size in arcsec, not a distance-dependent
  linear/physical resolution)


Note that the archive's TAP/ObsCore interface returns one row per spectral window, 
so a single observation can appear as several rows. For this task, "one observation" 
means one Member Observation Unit Set (MOUS), which is identified by the `member_ous_uid` column. 

<!-- NOTE: intentionally not specifying spatial or angular resolution due to naming ambiguity in the ObsCore schema -->
Write your findings to `/app/output.json` as a JSON object. Report the number of observations found and report, for each matching observation, at minimum: the project code, the band(s), and the resolution (in arcseconds). Field names and overall structure are up to you.

Exactly one row in "observations" per distinct member_ous_uid. You have internet access to the ALMA archive (almascience.org / almascience.nrao.edu / almascience.eso.org).