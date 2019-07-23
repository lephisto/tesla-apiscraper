# tesla-apiscraper
Selfhosted API Scraper for pulling Vehicle Telemetry from the Tesla Owner API into an InfluxDB visualisation on Grafana Dashboards.

Known to work with Model S, X and 3.

_Current Release: v2019.5_

**Putting an end to __handing out the Key__ for your 100+ Grand Car to a third party you don't know.**

This can be hosted on any System that's capable of running InfluxDB, Grafana and Python. In this short guide I assume you're using a Debian'ish OS. It can run on a dedicated Linuxserver out there on the Internets or on your home Raspberry Pi.

It also has it's own API for use with an Android app or your own custom implementation, this will make sure you can start/stop/resume scraping your car. The App for Android is available on [here on Google Play](https://play.google.com/store/apps/details?id=to.mephis.apiscrapercontrol)

The current App Version is 1.2.8

## Features

- Capable of handling multiple Vehicles in one Tesla Account
- Extended Sleep support: Car will fall asleep after certain time of no charging and no driving. Monitoring will continue withing 60 Seconds on car usage.
- Control, comes with built-in API for use with an Android app or custom implementation to stop/resume scraping


## Screenshots

![Driving Dashboard](https://raw.githubusercontent.com/lephisto/tesla-apiscraper/master/screenshots/teslametrics_v2_1.png)

![Charging Dashboard](https://raw.githubusercontent.com/lephisto/tesla-apiscraper/master/screenshots/teslametrics_v2_2.png)

Projected 100% Range:

![Projected Graph](https://raw.githubusercontent.com/lephisto/tesla-apiscraper/master/screenshots/teslametrics_v2_3.png)

## Installation:

*Note: This probably won't work on a Pi zero W, since ArmV6 is too weak.*

Build and run tesla-apiscraper via Docker.

1. Edit your settings in `config.py`, at least put in your MyTesla credentials. Do not edit the influx credentials! The docker script will automatically fill this out for you later.

```bash
git clone https://github.com/Lunars/tesla-apiscraper.git
cd tesla-apiscraper

# Create the config file
cp config.py.compose config.py

# Edit the file to insert your Tesla account credentials
nano config.py
```

2. Run the following to finish your docker setup

```bash
# Important: Create empty Log, otherwise bindmount will fail.
touch apiscraper.log

# Create Directories for persistent Data:
sudo mkdir -p /opt/apiscraper/influxdb
sudo mkdir -p /opt/apiscraper/grafana
sudo chown 472 /opt/apiscraper/grafana

# Update docker
curl -fsSL get.docker.com -o get-docker.sh && sh get-docker.sh
apt-get install docker-compose

# Start Docker Stack
./dashboard2docker.sh
docker-compose up -d

# Make the scraper start start on boot
cp tesla-apiscraper.service /lib/systemd/system
sudo systemctl daemon-reload
sudo systemctl enable tesla-apiscraper.service

# Add pi or any other user you would like to the Docker Group
usermod -aG docker pi
reboot
```

Done, you can now reach your Grafana Instance at http://localhost:3000


Both logfile (apiscraper.log) and the config file (config.py) are mapped outside the Docker container, so you can view / change these whenever you'd like. After changing, just restart the container.

If you ever want to update the stack:

```bash
docker-compose pull
docker-compose build --build-arg CACHEBUST=$(date +%s) apiscraper
docker-compose up --force-recreate --build
```

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
