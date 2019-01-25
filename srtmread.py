import os
import sys
import srtm
from pathlib import Path

def elevationtoinflux(lat, lon, vin, displayname, ts, ifclient, dryrun):
    if not os.path.isfile('srtm.lck.' + str(os.getpid())):
        Path('srtm.lck.' + str(os.getpid())).touch()
        elevation_data = srtm.get_data()
        elevation = elevation_data.get_elevation(lat, lon)
        os.remove('srtm.lck.' + str(os.getpid()))
        print("Elevation: " + str(elevation))
        elev_json_body = [
            {
                "measurement": "drive_state",
                "tags": {
                    "vin": vin,
                    "display_name": displayname,
                },
                "time": ts * 1000000000,
                "fields": {
                    "elevation": elevation
                }
            }
        ]
        if not dryrun:
            ifclient.write_points(elev_json_body)
    else:
        print("Lockfile detected, skipping")
    sys.exit()
