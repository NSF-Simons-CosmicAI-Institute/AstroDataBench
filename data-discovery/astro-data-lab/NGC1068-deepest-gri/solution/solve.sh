#!/bin/bash
set -euo pipefail

python3 - <<'EOF'
import json
import numpy as np

from astropy.coordinates import SkyCoord
from pyvo.dal import sia

DEF_ACCESS_URL = "https://datalab.noirlab.edu/sia/nsa"  # general NOIRLab Science Archive
svc = sia.SIAService(DEF_ACCESS_URL)

COORD = SkyCoord.from_name("NGC 1068")
RA_DEG, DEC_DEG = COORD.ra.deg, COORD.dec.deg
FOV = 0.1  #degrees
TARGET_BANDS = ["g", "r", "i"]

def get_deepest_stack_info(ra,dec,fov=0.1,band='g'):
    #Based on function in https://github.com/astro-datalab/notebooks-latest/blob/058d6a71dbdd7f4f19a38f5ec6f78cd9b107113c/01_GettingStartedWithDataLab/02_GettingStartedWithDataLab.ipynb
    imgTable = svc.search((ra,dec), (fov/np.cos(dec*np.pi/180), fov), verbosity=2).to_table()
    # add selection forthe desired bandpass
    sel0 = imgTable['obs_bandpass'] == band
    # add selections for 'Stack' and 'image' and level 3 product type 
    sel = sel0 & ((imgTable['proctype'] == 'Stack') & (imgTable['prodtype'] == 'image')) 
    Table = imgTable[sel] 

    # if multiple images match the criteria, pick the one with longest exposure time
    if (len(Table) > 0):
        row = Table[np.argmax(Table['exptime'].data.data.astype('float'))] 
        url = row['access_url'] # get the download URL
        return row
    # if no images match the criteria
    else:
        return None

output = []
for band in TARGET_BANDS:
    deepest_img_row = get_deepest_stack_info(RA_DEG, DEC_DEG, fov=FOV, band=band)
    output.append({'band':deepest_img_row['obs_bandpass'], 
                   'exptime': deepest_img_row['exptime'], 
                   'access_url': deepest_img_row['access_url']})


with open("/app/output.json", "w") as f:
    json.dump(output, f, indent=2)

EOF