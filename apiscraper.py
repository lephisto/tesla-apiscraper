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
import threading
import json
import Queue

from BaseHTTPServer import HTTPServer
from BaseHTTPServer import BaseHTTPRequestHandler
from io import BytesIO

from influxdb import InfluxDBClient
from pprint import pprint
from config import *

a_vin = ""
a_displayname = ""
a_ignore = ["media_state", "software_update", "speed_limit_mode"]

postq = Queue.Queue()

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
                self.vehicle = connection.vehicles[a_tesla_caridx]
                return self.vehicle
            except (KeyError, urllib2.HTTPError, urllib2.URLError) as details:
                delay *= 2
                logger.warning("HTTP Error:" + str(details))
                logger.info("Waiting %d seconds before retrying." % delay)
                time.sleep(delay)

    def request_state_group(self):
        global a_vin
        global a_displayname
        global a_ignore
        # Request and process all Tesla states
        any_change = False
        logger.info(">> Request vehicle data")
        r = self.vehicle.get("vehicle_data")

        for request in self.requests:
            header_printed = False
            result=r['response'][request]
            timestamp = result['timestamp']
            if self.old_values[request].get('timestamp', '') == timestamp:
                break
            self.old_values[request]['timestamp'] = timestamp
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
                                if not a_dryrun:
                                    influxclient.write_points(json_body)
                        self.old_values[request][element] = new_value
        return any_change

    def check_states(self, interval):
        # Check all Tesla States
        any_change = False
        try:
            if self.request_state_group():
                any_change = True
            else:
                shift = self.old_values['drive_state'].get('shift_state', '');
                if shift == "R" or shift == "D":
                    # We are actively driving, does not matter we are
                    # stopped at a traffic light or whatnot,
                    # keep polling
                    interval = 1
                    any_change = True

        except (urllib2.HTTPError, urllib2.URLError) as exc:
            logger.info("HTTP Error: " + str(exc))
            if a_allowsleep == 1:
                return interval
            else:
                return -1  # re-initialize.

        if interval == 0:
            interval = 1

        # If we are charging at a supercharger, it's worth polling frequently
        # since the changes are fast. For regular charging 16 seconds
        # interval seems to be doing ok on my 72A/16kW charger, perhaps
        # we can even poll every 32 seconds on 40A and below? Polling
        # based on values changing is not good because there's constant +-1V
        # jitter on the source power that results in needless overhead
        if self.old_values['charge_state'].get('charging_state', '') == "Charging":
            if self.old_values['charge_state'].get('fast_charger_present', '') == "true":
                interval = 2
            else:
                interval = 16

        # If we are not charging (and not moving), then we can use the
        # usual logic to determine how often to poll based on how much
        # activity we see.
        else:
            if any_change:  # there have been changes, reduce interval
                if interval > 1:
                    interval /= 2
            else:   # there haven't been any changes, increase interval to allow the car to fall asleep
                if interval < 2048:
                    interval *= 2
        return interval

def lastStateReport(f_vin):
    query="select time,state from vehicle_state where metric='state' and vin='"+ f_vin +"' order by time desc limit 1"
    influxresult = influxclient.query(query)
    point = list(influxresult.get_points(measurement='vehicle_state'))
    return(point[0])

# HTTP Thread Handler
class apiHandler(BaseHTTPRequestHandler):

    def do_HEAD(s):
        s.send_response(200)
        s.send_header("Content-type", "application/json")
        s.end_headers()

    def do_GET(s):
        if s.path == "/state" and s.headers.get('apikey') == a_apikey:
            s.send_response(200)
            api_response = [
                {
                    "result": "ok",
                    "vin": a_vin,
                    "apikey": a_apikey,
                    "displayname": a_displayname,
                    "state": is_asleep,
                    "disablescraping": s.server.api_disablescrape,
                    "disabledsince": s.server.api_disabledsince,
                    "interval": s.server.api_poll_interval
                }
            ]
        else:
            s.send_response(400)
            api_response = [
                {
                    "result": "fail"
                }
            ]
        s.send_header("Content-type", "application/json")
        s.end_headers()
        s.wfile.write(json.dumps(api_response, indent=4))

    #todo
    def do_POST(s):
        if s.path == "/switch" and s.headers.get('apikey') == a_apikey:
            content_length = int(s.headers['Content-Length'])
            body = s.rfile.read(content_length)
            if command != None:
                s.send_response(200)
                s.server.pqueue.put(body)
            else:
                s.send_response(401)
        else:
            s.send_response(400)
        s.end_headers()

class QueuingHTTPServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, pqueue, bind_and_activate=True):
        HTTPServer.__init__(self, server_address, RequestHandlerClass, bind_and_activate)
        self.pqueue = postq

def run_server(port, pq):
    print('run_server')
    httpd = QueuingHTTPServer(('0.0.0.0', port), apiHandler, pq)
    while True:
        print("HANDLE: " + threading.current_thread().name)
        httpd.api_disablescrape = disableScrape
        httpd.api_poll_interval = poll_interval
        httpd.api_disabledsince = disabledsince
        httpd.handle_request()


if __name__ == "__main__":
    # Create Tesla API Interface
    state_monitor = StateMonitor(a_tesla_email, a_tesla_passwd)
    poll_interval = 1   # Set to -1 to wakeup the Car on Scraper start
    asleep_since = 0
    is_asleep = ''
    disableScrape = a_start_disabled
    disabledsince = 0
    # Create HTTP Server Thread
    if (a_enableapi):
        thread = threading.Thread(target=run_server, args=(a_apiport,postq))
        thread.daemon = True
        try:
            thread.start()
            logger.info("HTTP Server Thread started on port " + str(a_apiport))
        except KeyboardInterrupt:
            server.shutdown()
            sys.exit(0)

# XXX - this is to make sure we have it initialized for the uses below
# if we did not call into is_asleep() (Which we did not since we start with
# a small interval
vehicle_state = state_monitor.is_asleep()

# Main Program Loop. messy..
while True:
    if not postq.empty():
        command = json.loads(postq.get())
        pprint(command)
        disableScrape = command['value']
        if not disableScrape:
            poll_interval = 1

    if disableScrape == False:
        disabledsince = 0
        # We cannot be sleeping with small poll interval for sure.
        # In fact can we be sleeping at all if scraping is enabled?
        if poll_interval >= 64:
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
        if not a_dryrun:
            influxclient.write_points(state_body)
        logger.info("Car State: " + is_asleep +
                    " Poll Interval: " + str(poll_interval))
        if is_asleep == 'asleep' and a_allowsleep == 1:
            logger.info("Car is probably asleep, we let it sleep...")
            poll_interval = 64
            asleep_since += poll_interval

        if poll_interval > 0:
            logger.info("Asleep since: " + str(asleep_since) +
                        " Sleeping for " + str(poll_interval) + " seconds..")
            time.sleep(poll_interval - time.time() % poll_interval)
            poll_interval = state_monitor.check_states(poll_interval)
        elif poll_interval < 0:
            state_monitor.wake_up()
            poll_interval = 1
        else:
            time.sleep(1)
    else:
        disabledsince += 1
        time.sleep(1)
    sys.stdout.flush()
