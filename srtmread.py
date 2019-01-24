import os
import sys
import numpy as np
import urllib2
import zipfile
import threading
from pathlib import Path

SAMPLES = 1201  # Change this to 3601 for SRTM1
HGTDIR = 'hgt'  # All 'hgt' files will be kept here uncompressed
HGT_EURASIA = 'https://dds.cr.usgs.gov/srtm/version1/Eurasia/'


def elevationtoinflux(lat, lon, vin, displayname, ts, ifclient, dryrun):
    print("elevationtoinflux vars: " + str(ts))
    hgt_file = get_file_name(lat, lon)
    if hgt_file:
        elevation = read_elevation_from_file(hgt_file, lon, lat)
        elev_json_body = [
            {
                "measurement": "drive_state",
                "tags": {
                    "vin": vin,
                    "display_name": displayname,
                },
                "time": ts * 1000000,
                "fields": {
                    "elevation": elevation
                }
            }
        ]
        if not dryrun:
            ifclient.write_points(elev_json_body)
            elev_json_body
        print("HANDLE: " + threading.current_thread().name + " elevation: " + str(elevation))
        sys.exit()

    return True


def read_elevation_from_file(hgt_file, lon, lat):
    with open(hgt_file, 'rb') as hgt_data:
        # HGT is 16bit signed integer(i2) - big endian(>)
        elevations = np.fromfile(hgt_data, np.dtype('>i2'), SAMPLES*SAMPLES)\
                                .reshape((SAMPLES, SAMPLES))
        lat_row = int(round((lat - int(lat)) * (SAMPLES - 1), 0))
        lon_row = int(round((lon - int(lon)) * (SAMPLES - 1), 0))
        return elevations[SAMPLES - 1 - lat_row, lon_row].astype(int)


def get_file_name(lat, lon):
    if lat >= 0:
        ns = 'N'
    elif lat < 0:
        ns = 'S'
    if lon >= 0:
        ew = 'E'
    elif lon < 0:
        ew = 'W'
    hgt_file = "%(ns)s%(lat)02d%(ew)s%(lon)03d.hgt" % {'lat': abs(lat), 'lon': abs(lon), 'ns': ns, 'ew': ew}
    hgt_file_path = os.path.join(HGTDIR, hgt_file)
    if os.path.isfile(hgt_file_path):
        return hgt_file_path
    else:
        if not os.path.isfile(hgt_file_path + ".zip.downloading"):
            print("Don't have it, downloading: " + HGT_EURASIA + hgt_file + '.zip' + " to " + hgt_file_path + '.zip')
            try:
                Path(hgt_file_path + '.zip.downloading').touch()
                response = urllib2.urlopen(HGT_EURASIA + hgt_file + '.zip')
                data = response.read()
                file_ = open (hgt_file_path + '.zip', 'w')
                file_.write(data)
                file_.close()
                zip_ = zipfile.ZipFile(hgt_file_path + '.zip')
                zip_.extractall(HGTDIR)
                zip_.close()
                os.remove(hgt_file_path + '.zip.downloading')
                return hgt_file_path
            except urllib2.HTTPError as e:
                print("HTTP Error:", e.code, e.url)
            except urllib2.URLError as e:
                print("URL Error:", e.reason, e.url)
            return None
        else:
            print("Thread aborting, downloading already")
            return None
