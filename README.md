<h1 align="center">Welcome to Tesla API Scraper 👋</h1>

> Putting an end to handing out the Key for your >$100k car to a third party you don't know.

Selfhosted API Scraper for pulling Vehicle Telemetry from the Tesla Owner API into an InfluxDB visualisation on Grafana Dashboards.

Known to work with Model S, X and 3. Capable of handling multiple Vehicles in one Tesla Account

## Install

*Note: This probably won't work on a Pi zero W, since ArmV6 is too weak.*

1. Edit your settings in `config.py`, at least put in your MyTesla credentials. Do not edit the influx credentials! The docker script will automatically fill that out for you later.

```bash
# Enter your email and password to your tesla.com account
teslaEmail=""
teslaPassword=""

curl -sL "https://git.io/fjD3b?$(date +%s)" > install && bash install $teslaEmail $teslaPassword
```

Your system will reboot, and then you can reach your Grafana Instance at http://localhost:3000

Default u/p is admin/admin

Both logfile (apiscraper.log) and the config file (config.py) are mapped outside the Docker container, so you can view / change these whenever you'd like. After changing, just restart the container.

If you ever want to update the stack:

```bash
docker-compose pull
docker-compose build --build-arg CACHEBUST=$(date +%s) apiscraper
docker-compose up --force-recreate --build
```

## Screenshots

![Driving Dashboard](https://raw.githubusercontent.com/lephisto/tesla-apiscraper/master/screenshots/teslametrics_v2_1.png)

![Charging Dashboard](https://raw.githubusercontent.com/lephisto/tesla-apiscraper/master/screenshots/teslametrics_v2_2.png)

![Projected Graph](https://raw.githubusercontent.com/lephisto/tesla-apiscraper/master/screenshots/teslametrics_v2_3.png)

## Known Limitations and issues

- If you narrow down Timefilter too much, and there are no Measurements, you won't see anything in the Graph and Discrete.
- The Code is far from being clean and in some way spaghetti'ish. This will be cleaned up in future Versions.
- Boolean Values from the API currently won't show

## Some remarks about the APIScraper

- As stated below, the API is crafted for being used by the ios or android app. One challenge was to implement a reliable sleepmode. If the car is awake, the API keeps it awake, as long as requests occur. Once it falls asleep, parts of the API can be called to check the sleep state without waking up the car, however, when the scraper detects that the car doesn't change Values (not driving, not charging), it increases the Poll interval until the Car falls asleep. Once it's asleep it checks the sleepstate every Minute. This ensures, that the stats don't miss relevant portions of rides when the car was just woken up, an issue some other monitoring implementations suffer from.

## More Disclaimer

- Please note that the use of the Tesla REST API in general and the use of this software in particular is not endorsed by Tesla. You use this software at your own risk. The author does not take responsibility for anything related to the use of this software.

## Roadmap

- Multithreaded statpulling
- Code Cleanup (feel free to send PR :)
- Move from influxql to it's successor flux, the upcoming query language for InfluxDB
- Write some Tickscripts for alerting
- Have a color gradient on geolocation that reflects any metric like speed for instance
- Improve sleepinitiation

## Credits

- Tesla API Interface forked from Greg Glockner https://github.com/gglockner/teslajson (removed pulling Tesla API Credentials from a pastebin whish seemed fishy..)
- Things stolen from basic Script from cko from the german tff-forum.de
