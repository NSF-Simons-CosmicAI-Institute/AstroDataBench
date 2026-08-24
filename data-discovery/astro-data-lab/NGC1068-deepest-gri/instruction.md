I want to create a three-color composite image of the galaxy NGC 1068 using the deepest g, r, and i-band stacked images available on the NOIRLab Science Archive. Find and report which images I should use.

Write your report to `/app/output.json` as a JSON object, where each row contains (at minimum) the band, access URL, and exposure time (in seconds) for one image. Field names are up to you.

You have internet access to the NOIRLab Astro Data Lab platform
(datalab.noirlab.edu) and PyPI. `pyvo`, `astroquery`, and `datalab` are
already installed.