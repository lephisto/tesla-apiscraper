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

import json
import logging
import queue
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.error import URLError

from influxdb import InfluxDBClient
from urllib3.exceptions import HTTPError

import teslajson
from config import *
from srtmread import elevationtoinflux

a_vin = ""
a_display_name = ""
a_ignore = ["media_state", "software_update", "speed_limit_mode"]

postq = queue.Queue()
http_condition = threading.Condition()

poll_interval = 1  # Set to -1 to wakeup the Car on Scraper start
asleep_since = 0
is_asleep = ''
disableScrape = a_start_disabled
disabled_since = 0
busy_since = 0
car_active_state = None
resume = False

# DON'T CHANGE ANYTHING BELOW
scraperapi_version = 2019.2

influx_client = InfluxDBClient(
    a_influx_host, a_influx_port, a_influx_user, a_influx_pass, a_influx_db)


def setup_custom_logger(name):
    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    handler = logging.FileHandler(a_logfile, mode='a')
    handler.setFormatter(formatter)
    screen_handler = logging.StreamHandler(stream=sys.stdout)
    screen_handler.setFormatter(formatter)
    custom_logger = logging.getLogger(name)
    custom_logger.setLevel(logging.DEBUG)
    custom_logger.addHandler(handler)
    custom_logger.addHandler(screen_handler)
    return custom_logger


logger = setup_custom_logger('apiscraper')


class StateMonitor(object):
    """ Monitor all Tesla states."""

    def __init__(self, tesla_email, tesla_password):
        self.requests = ("charge_state", "climate_state", "drive_state",
                         "gui_settings", "vehicle_state")
        self.priority_requests = {1: ("drive_state",),
                                  2: ("drive_state",),
                                  4: ("charge_state", "drive_state",)}
        self.old_values = dict([(r, {}) for r in self.requests])

        self.connection = teslajson.Connection(tesla_email, tesla_password)
        self.vehicle = self.connection.vehicles[a_tesla_car_idx]

    def refresh_vehicle(self):
        # refreshes the vehicle object
        logger.info(">> self.connection.refresh_vehicle()")
        self.connection.refresh_vehicle()
        self.vehicle = self.connection.vehicles[a_tesla_car_idx]

    def ongoing_activity_status(self):
        """ True if the car is not in park, or is actively charging ... """
        shift = self.old_values['drive_state'].get('shift_state', '')
        old_speed = self.old_values['drive_state'].get('speed', 0) or 0
        if shift == "R" or shift == "D" or shift == "N" or old_speed > 0:
            return "Driving"
        if self.old_values['charge_state'].get('charging_state', '') in [
            "Charging", "Starting"]:
            return "Charging"
        # If we just completed the charging, need to wait for voltage to
        # go down to zero too to avoid stale value in the DB.
        if (self.old_values['charge_state'].get('charging_state', '') == "Complete" or self.old_values[
            'charge_state'].get('charging_state', '') == "Stopped") \
                and self.old_values['charge_state'].get('charger_voltage', 0) > 100:
            return "Charging"

        if self.old_values['climate_state'].get('is_climate_on', False):
            return "Conditioning"
        # When it's about time to start charging, we want to perform
        # several polling attempts to ensure we catch it starting even
        # when scraping is otherwise disabled
        if self.old_values['charge_state'].get('scheduled_charging_pending', False):
            scheduled_time = self.old_values['charge_state'].get('scheduled_charging_start_time', 0)
            if abs(scheduled_time - int(time.time())) <= 2:
                return "Charging"

        # If screen is on, the car is definitely not sleeping so no
        # harm in polling it as long as values are changing
        if self.old_values['vehicle_state'].get('center_display_state', 0) != 0:
            return "Screen On"

        return None

    def wake_up(self):
        """ mod """
        global a_vin
        global a_display_name
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
                        a_display_name = result[element]
                return
            except (KeyError, HTTPError, URLError) as details:
                delay *= 2
                logger.warning("HTTP Error:" + str(details))
                logger.info("Waiting %d seconds before retrying." % delay)
                time.sleep(delay)

    def update_vehicle_from_response(self, response):
        # The other vehicle items are pretty much static.
        # We don't need to do any db insertions here, the main loop
        # would perform those for us.
        for item in ["state", "display_name"]:
            self.vehicle[item] = response[item]

    def request_state_group(self):
        global a_vin
        global a_display_name
        global a_ignore
        a_lat = None
        a_long = None
        # Request and process all Tesla states
        any_change = False
        logger.info(">> Request vehicle data")
        r = self.vehicle.get("vehicle_data")

        self.update_vehicle_from_response(r['response'])

        for request in self.requests:
            header_printed = False
            result = r['response'][request]
            timestamp = result['timestamp']
            if self.old_values[request].get('timestamp', '') == timestamp:
                break
            self.old_values[request]['timestamp'] = timestamp
            for element in sorted(result):
                if element not in (
                        "timestamp", "gps_as_of", "left_temp_direction", "right_temp_direction", "charge_port_latch"):
                    old_value = self.old_values[request].get(element, '')
                    new_value = result[element]
                    if element == "vehicle_name" and not new_value:
                        continue
                    if element == "native_latitude":
                        a_lat = new_value
                    if element == "native_longitude":
                        a_long = new_value
                    if new_value and old_value and ((element == "inside_temp") or (element == "outside_temp")):
                        if abs(new_value - old_value) < 1.0:
                            new_value = old_value
                            logger.info(
                                "Only minimal temperature difference received. No change registered to avoid wakelock.")
                    if new_value and old_value and (
                            (element == "battery_range") or
                            (element == "est_battery_range") or
                            (element == "ideal_battery_range")
                    ):
                        if abs(new_value - old_value) < 0.5:
                            new_value = old_value
                            logger.info(
                                "Only minimal range difference received. No change registered to avoid wakelock.")
                    if (old_value == '') or ((new_value is not None) and (new_value != old_value)):
                        logger.info("Value Change, SG: " + request + ": Logging..." + element +
                                    ": old value: " + str(old_value) + ", new value: " + str(new_value))
                        if not header_printed:
                            timestamp = None
                            if "timestamp" in result:
                                timestamp = result["timestamp"] / 1000
                            header_printed = True
                            any_change = True
                        if new_value is not None:
                            if element not in a_ignore:
                                json_body = [
                                    {
                                        "measurement": request,
                                        "tags": {
                                            "vin": a_vin,
                                            "display_name": a_display_name,
                                            "metric": element
                                        },
                                        "time": int(timestamp) * 1000000000,
                                        "fields": {
                                            element: new_value
                                        }
                                    }
                                ]
                                if not a_dry_run:
                                    influx_client.write_points(json_body)
                        self.old_values[request][element] = new_value
                if a_lat is not None and a_long is not None and a_resolve_elevation:
                    # Fire and forget Elevation retrieval..
                    print("starting thread elevator: " + str(a_lat) + "/" + str(a_long) + "/" + str(timestamp))
                    elevator = threading.Thread(target=elevationtoinflux,
                                                args=(
                                                    a_lat, a_long, a_vin, a_display_name,
                                                    timestamp, influx_client, a_dry_run))
                    # elevator.daemon = True
                    elevator.setName("elevator")
                    if not elevator.is_alive():
                        elevator.start()
                    a_lat = None
                    a_long = None
        return any_change

    def check_states(self, interval):
        # Check all Tesla States
        any_change = False
        try:
            if self.request_state_group():
                any_change = True
            else:
                shift = self.old_values['drive_state'].get('shift_state', '')
                if shift == "R" or shift == "D":
                    # We are actively driving, does not matter we are
                    # stopped at a traffic light or whatnot,
                    # keep polling
                    interval = 1
                    any_change = True

        except (HTTPError, URLError) as exc:
            logger.info("HTTP Error: " + str(exc))
            if a_allow_sleep == 1:
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
            else:  # there haven't been any changes, increase interval to allow the car to fall asleep
                if interval < 2048:
                    interval *= 2
        return interval


def last_state_report(f_vin):
    raw_query = "select time,state from vehicle_state where metric='state' and vin='{}' order by time desc limit 1"
    query = raw_query.format(f_vin)
    influx_result = influx_client.query(query)
    point = list(influx_result.get_points(measurement='vehicle_state'))
    return point[0]


# HTTP Thread Handler
class ApiHandler(BaseHTTPRequestHandler):

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()

    def do_GET(self):
        if self.path == "/state" and self.headers.get('apikey') == a_api_key:
            self.send_response(200)
            busy_since_copy = busy_since
            if busy_since_copy:
                processing_time = int(time.time()) - busy_since_copy
            else:
                processing_time = 0
            api_response = [
                {
                    "result": "ok",
                    "vin": a_vin,
                    "scraperapiversion": scraperapi_version,
                    "displayname": a_display_name,
                    "state": is_asleep,
                    "disablescraping": disableScrape,
                    "carstate": car_active_state,
                    "disabled_since": disabled_since,
                    "interval": poll_interval,
                    "busy": processing_time
                }
            ]
        else:
            self.send_response(400)
            api_response = [
                {
                    "result": "fail"
                }
            ]
        self.send_header("Content-type", "application/json")
        self.end_headers()
        byt = json.dumps(api_response, indent=4).encode()
        self.wfile.write(byt)

    # todo
    def do_POST(self):
        if self.path == "/switch" and self.headers.get('apikey') == a_api_key:
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            post_command = json.loads(body)
            if post_command['command'] is not None:
                self.send_response(200)
                self.server.condition.acquire()
                self.server.pqueue.put(body)
                self.server.condition.notify()
                self.server.condition.release()
            else:
                self.send_response(401)
        else:
            self.send_response(400)
        self.end_headers()


class QueuingHTTPServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, pqueue, cond, bind_and_activate=True):
        HTTPServer.__init__(self, server_address, RequestHandlerClass, bind_and_activate)
        self.pqueue = postq
        self.condition = cond


def run_server(port, pq, cond):
    httpd = QueuingHTTPServer(('0.0.0.0', port), ApiHandler, pq, cond)
    while True:
        print("HANDLE: " + threading.current_thread().name)
        httpd.handle_request()


if __name__ == "__main__":
    # Create Tesla API Interface
    try:
        state_monitor = StateMonitor(a_tesla_email, a_tesla_password)
    except:
        sys.exit("Failed to initialize Owner API")
    main_loop_count = 0

    # Create HTTP Server Thread
    if a_enable_api:
        thread = threading.Thread(target=run_server, args=(a_api_port, postq, http_condition))
        thread.daemon = True
        try:
            thread.start()
            logger.info("HTTP Server Thread started on port " + str(a_api_port))
        except KeyboardInterrupt:
            sys.exit(0)
    elif disableScrape:
        sys.exit("Configuration error: Scraping disabled and no api configured to enable. Bailing out")

# Main Program Loop. messy..
while True:

    # We need to store this state in this global variable to ensure
    # HTTP thread is able to see it in real time as well.
    car_active_state = state_monitor.ongoing_activity_status()

    # Look if there's something from the Webservers Post Queue
    while not postq.empty():
        req = json.loads(postq.get())
        command = req['command']
        if command == "scrape":
            disableScrape = req['value']
            if not disableScrape:
                logger.info("Resume Scrape requested")
                poll_interval = 1
                disabled_since = 0
                resume = True
            else:
                logger.info("Stop Scrape requested")
                disabled_since = (int(time.time()))
        if command == "oneshot":
            # Just override the car_active_state for a single
            # round of requests
            car_active_state = "oneshot request"
            logger.info("Oneshot update requested")
            if is_asleep == "asleep":
                logger.info("Waking the car up for the oneshot request")
                state_monitor.wake_up()
                resume = True

    if disableScrape is False or car_active_state is not None:
        busy_since = int(time.time())
        # We cannot be sleeping with small poll interval for sure.
        # In fact can we be sleeping at all if scraping is enabled?
        if poll_interval >= 64 or resume:
            state_monitor.refresh_vehicle()
        # Car woke up
        if is_asleep == 'asleep' and state_monitor.vehicle['state'] == 'online':
            poll_interval = 0
            asleep_since = 0

        if state_monitor.vehicle['state'] == 'asleep' and is_asleep == 'online':
            asleep_since = time.time()

        is_asleep = state_monitor.vehicle['state']
        a_vin = state_monitor.vehicle['vin']
        a_display_name = state_monitor.vehicle['display_name']
        ts = int(time.time()) * 1000000000
        state_body = [
            {
                "measurement": 'vehicle_state',
                "tags": {
                    "vin": state_monitor.vehicle['vin'],
                    "display_name": state_monitor.vehicle['display_name'],
                    "metric": 'state'
                },
                "time": ts,
                "fields": {
                    "state": is_asleep
                }
            }
        ]
        if not a_dry_run:
            influx_client.write_points(state_body)
        logger.info("Car State: " + is_asleep +
                    " Poll Interval: " + str(poll_interval))
        if is_asleep == 'asleep' and a_allow_sleep == 1:
            logger.info("Car is probably asleep, we let it sleep...")
            poll_interval = 64

        if poll_interval >= 0:
            if is_asleep != 'asleep':
                poll_interval = state_monitor.check_states(poll_interval)
                resume = False
        elif poll_interval < 0:
            state_monitor.wake_up()
            poll_interval = 1
        to_sleep = poll_interval
        processing_time = int(time.time()) - busy_since
        # If we spent too much time in processing, warn here
        # Reasons might be multiple like say slow DB or slow tesla api
        if processing_time > 10:
            logger.info("Too long processing loop: " + str(processing_time) +
                        " seconds... Tesla server or DB slow?")
        logger.info("Asleep since: " + str(asleep_since) +
                    " Sleeping for " + str(poll_interval) + " seconds..")
        busy_since = 0
    else:
        # If we have scheduled charging, lets wake up just in time
        # to catch that activity.
        if state_monitor.old_values['charge_state'].get('scheduled_charging_pending', False):
            to_sleep = state_monitor.old_values['charge_state'].get('scheduled_charging_start_time', 0) - int(
                time.time())
            # This really should not happen
            if to_sleep <= 0:
                to_sleep = None
            else:
                logger.info("Going to sleep " + str(to_sleep) + " seconds until a scheduled charge")
        else:
            to_sleep = None

    # Look if there's something from the Webservers Post Queue
    http_condition.acquire()
    if not postq.empty():
        # Need to turn around and do another round of processing
        # right away.
        http_condition.release()
        continue

    # Using to_sleep value ensures we don't miss the active car state here
    # even if disableScrape changed to true. Do not directly check it
    # here without checking for state_monitor.ongoing_activity_status()
    http_condition.wait(to_sleep)
    http_condition.release()
    # A wakeup here due to http request coming might cause a long sleep
    # to be interrupted early on and if no activity happened in the car,
    # double it, that's probably an ok condition that we should not care
    # too much about since it's guaranteed to be a "stop scraping" case
    # anyway ("start scraping" would reset poll interval to 1 and we'll
    # start quick polling anyway)
    # Same thing applies to the continue case above

    sys.stdout.flush()
