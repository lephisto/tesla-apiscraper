""" apiscraper.py - log all Tesla data available from the
    Mothership API to Influx.

    Author: Bastian Maeuser
    https://github.com/lephisto/tesla-apiscraper

    Please note that the use of the Tesla REST API in general
    and the use of this software in particular is not endorsed by Tesla.
    You use this software at your own risk.
    The author does not take responsibility for anything related
    to the use of this software.

    Thanks go to cko from the german tff-forum for a basic version of the
    script.

    Configuration is taken from config.py - a sample file is distributed as
    config.py.dist. Rename it and configure it according your needs.

"""

import os
import sys
import time
import urllib2
import teslajson
import logging

from influxdb import InfluxDBClient
from pprint import pprint
from config import *

a_vin = ""
a_displayname = ""
a_ignore = ["media_state", "software_update", "speed_limit_mode"]

influxclient = InfluxDBClient(
    a_influxhost, a_influxport, a_influxuser, a_influxpass, a_influxdb)


def setup_custom_logger(name):
    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    handler = logging.FileHandler(a_logfile, mode='a')
    handler.setFormatter(formatter)
    screen_handler = logging.StreamHandler(stream=sys.stdout)
    screen_handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.addHandler(screen_handler)
    return logger


logger = setup_custom_logger('apiscraper')


class StateMonitor(object):

    """ Monitor all Tesla states."""

    def __init__(self, a_tesla_email, a_tesla_passwd):
        self.requests = ("charge_state", "climate_state", "drive_state",
                         "gui_settings", "vehicle_state")
        self.priority_requests = {1: ("drive_state", ),
                                  2: ("drive_state", ),
                                  4: ("charge_state", "drive_state", )}
        self.old_values = dict([(r, {}) for r in self.requests])

        connection = teslajson.Connection(a_tesla_email, a_tesla_passwd)
        self.vehicle = connection.vehicles[a_tesla_caridx]

    def wake_up(self):
        """ mod """
        global a_vin
        global a_displayname
        """ end mod """
        """ Request wake up of car. """
        delay = 1
        while True:
            try:
                result = self.vehicle.wake_up()["response"]
                logger.info("wake_up")
                for element in sorted(result):
                    logger.debug("   %s=%s" % (element, result[element]))
                    """ mod """
                    if element == "vin":
                        a_vin = result[element]
                    if element == "display_name":
                        a_displayname = result[element]
                return
            except (KeyError, urllib2.HTTPError, urllib2.URLError) as details:
                delay *= 2
                logger.warning("HTTP Error:" + str(details))
                logger.info("Waiting %d seconds before retrying." % delay)
                time.sleep(delay)

    def is_asleep(self):
        delay = 1
        while True:
            try:
                logger.info("Getting vehicle state")
                connection = teslajson.Connection(
                    a_tesla_email, a_tesla_passwd)
                self.vehicle = connection.vehicles[0]
                return self.vehicle
            except (KeyError, urllib2.HTTPError, urllib2.URLError) as details:
                delay *= 2
                logger.warning("HTTP Error:" + str(details))
                logger.info("Waiting %d seconds before retrying." % delay)
                time.sleep(delay)

    def request_state_group(self, request):
        global a_vin
        global a_displayname
        global a_ignore
        # Request and process one group of Tesla states.
        header_printed = False
        any_change = False
        logger.info(">> Request Data: " + request)
        result = self.vehicle.data_request(request)
        for element in sorted(result):
            if element not in ("timestamp", "gps_as_of", "left_temp_direction", "right_temp_direction"):
                old_value = self.old_values[request].get(element, '')
                new_value = result[element]
                if ((old_value == '') or ((new_value is not None) and (new_value != old_value))):
                    logger.info("Value Change, SG: " + request + ": Logging..." + element +
                                ": old value: " + str(old_value) + ", new value: " + str(new_value))
                    if not header_printed:
                        timestamp = None
                        if "timestamp" in result:
                            timestamp = result["timestamp"] / 1000
                        header_printed = True
                        any_change = True
                    if new_value != None:
                        if element not in a_ignore:
                            json_body = [
                                {
                                    "measurement": request,
                                    "tags": {
                                        "vin": a_vin,
                                        "display_name": a_displayname,
                                        "metric": element
                                    },
                                    "time": timestamp * 1000000000,
                                    "fields": {
                                        element: new_value
                                    }
                                }
                            ]
                            influxclient.write_points(json_body)
                    self.old_values[request][element] = new_value
        return any_change

    def check_states(self, interval):
        # Check all Tesla States
        any_change = False
        for request in self.priority_requests.get(interval, self.requests):
            try:
                if interval > 32 and (request == "drive_state" or request == "charge_state"):
                    if self.request_state_group(request):
                        any_change = True
                        if request == "drive_state":
                            interval = 1
                elif interval <= 32:
                    if self.request_state_group(request):
                        any_change = True
                        if request == "drive_state":
                            interval = 1
            except (urllib2.HTTPError, urllib2.URLError) as exc:
                logger.info("HTTP Error: " + str(exc))
                if a_allowsleep == 1:
                    return interval
                else:
                    return -1  # re-initialize.
        if any_change:  # there have been changes, reduce interval
            if interval > 1:
                interval /= 2
        else:   # there haven't been any changes, increase interval to allow the car to fall asleep
            if interval < 512:
                interval *= 2
        return interval


if __name__ == "__main__":
    state_monitor = StateMonitor(a_tesla_email, a_tesla_passwd)
    poll_interval = 0   # Set to -1 to wakeup the Car on Scraper start
    asleep_since = 0
    is_asleep = ''

while True:
    vehicle_state = state_monitor.is_asleep()
    # Car woke up
    if is_asleep == 'asleep' and vehicle_state['state'] == 'online':
        poll_interval = 0
    is_asleep = vehicle_state['state']
    a_vin = vehicle_state['vin']
    a_displayname = vehicle_state['display_name']
    ts = int(time.time()) * 1000000000
    state_body = [
        {
            "measurement": 'vehicle_state',
            "tags": {
                "vin": vehicle_state['vin'],
                "display_name": vehicle_state['display_name'],
                "metric": 'state'
            },
            "time": ts,
            "fields": {
                "state": is_asleep
            }
        }
    ]
    influxclient.write_points(state_body)
    logger.info("Car State: " + is_asleep +
                " Poll Interval: " + str(poll_interval))
    if is_asleep == 'asleep' and a_allowsleep == 1:
        logger.info("Car is probably asleep, we let it sleep...")
        poll_interval = 64
        asleep_since += poll_interval

    if poll_interval > 1:
        logger.info("Asleep since: " + str(asleep_since) +
                    " Sleeping for " + str(poll_interval) + " seconds..")
        time.sleep(poll_interval - time.time() % poll_interval)
    elif poll_interval < 0:
        state_monitor.wake_up()
        poll_interval = 1

    if poll_interval < 512:
        poll_interval = state_monitor.check_states(poll_interval)
    elif poll_interval < 2048 and is_asleep != 'asleep':
        poll_interval *= 2
    sys.stdout.flush()
