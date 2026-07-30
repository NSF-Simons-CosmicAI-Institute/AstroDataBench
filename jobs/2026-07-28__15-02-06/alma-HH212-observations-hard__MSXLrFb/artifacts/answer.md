# HH212 Band 7 Sub-Arcsecond Continuum Data

I searched the ALMA Science Archive around HH212's resolved position (RA=85.96421, Dec=-1.04808, 60.0" radius) for public, science-grade Band 7 observations with a synthesized beam better than 1 arcsecond. This turned up **11 distinct observations** (grouped by ALMA Member OUS, since a single observation can span multiple spectral windows in the archive).

## Matching observations

- **2015.1.00024.S** (MOUS `uid://A001/X2de/X42`), observed 2015-11-05: 0.015" resolution, 3281250000.00 GHz continuum bandwidth, 33748s integration time.
- **2017.1.00044.S** (MOUS `uid://A001/X1273/X1f9`), observed 2017-11-27: 0.032" resolution, 7875000000.00 GHz continuum bandwidth, 24603s integration time.
- **2016.1.01475.S** (MOUS `uid://A001/X88f/X259`), observed 2016-10-06: 0.092" resolution, 2578125000.00 GHz continuum bandwidth, 109680s integration time.
- **2015.1.00041.S** (MOUS `uid://A001/X340/X1f9`), observed 2016-09-04: 0.092" resolution, 5171875000.00 GHz continuum bandwidth, 194s integration time.
- **2015.1.00037.S** (MOUS `uid://A001/X2de/X22`), observed 2016-08-30: 0.113" resolution, 8000000000.00 GHz continuum bandwidth, 9483s integration time.
- **2012.1.00122.S** (MOUS `uid://A002/X7b15a9/X5a`), observed 2015-08-11: 0.142" resolution, 3281250000.00 GHz continuum bandwidth, 4475s integration time.
- **2012.1.00997.S** (MOUS `uid://A002/X6ac013/X11`), observed 2014-06-15: 0.293" resolution, 3750000000.00 GHz continuum bandwidth, 30119s integration time.
- **2016.1.01475.S** (MOUS `uid://A001/X88f/X25b`), observed 2016-11-26: 0.338" resolution, 2578125000.00 GHz continuum bandwidth, 33022s integration time.
- **2011.0.00647.S** (MOUS `uid://A002/X36d874/X13`), observed 2012-11-02: 0.462" resolution, 7500000000.00 GHz continuum bandwidth, 14515s integration time.
- **2011.0.00647.S** (MOUS `uid://A002/X36d874/X11`), observed 2012-11-02: 0.471" resolution, 1875000000.00 GHz continuum bandwidth, 2675s integration time.
- **2019.1.00086.S** (MOUS `uid://A001/X1473/Xbe6`), observed 2019-12-09: 0.803" resolution, 6093750000.00 GHz continuum bandwidth, 1693s integration time.

## Suitability for a deep, high-resolution continuum image

The 2015.1.00024.S observation (MOUS `uid://A001/X2de/X42`) has the best resolution at 0.015" and 3281250000.00 GHz of continuum bandwidth, making it the strongest single candidate for a deep image on its own. 
Combining visibilities from multiple projects targeting HH212 could in principle deepen the image (lower the noise, improve uv-coverage), but this requires checking that their array configurations, spectral setups, and calibration are compatible before concatenating the measurement sets -- projects observed at different epochs or with different antenna configurations may not combine cleanly without careful re-calibration and re-weighting.