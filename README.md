# tesla-apiscraper
Selfhosted API Scraper for pulling Vehicle Telemetry from the Tesla Owner API into an InfluxDB visualisation on Grafana Dashboards.

**Putting an end to __handing out the Key__ for your 100+ Grand Car to a third party you don't know.**

This can be hosted on any System that's capable of running InfluxDB, Grafana and Python. In this short guide I assume you're using a Debian'ish OS. It can run on a dedicated Linuxserver out there on the Internets or on your home Raspberry Pi.

## Screenshots

![Driving Dashboard](https://raw.githubusercontent.com/lephisto/tesla-apiscraper/master/screenshots/driving_dash.png)

![Charging Dashboard](https://raw.githubusercontent.com/lephisto/tesla-apiscraper/master/screenshots/charging_dash.png)

## Installation:

- Install Python

eg:
```
sudo apt install python
```

- Install InfluxDB as in https://docs.influxdata.com/influxdb/v1.7/introduction/installation/ and create a Database where you want to store your Data in:

```
user@horst:~$ influx
Connected to http://localhost:8086 version 1.7.2
InfluxDB shell version: 1.7.2
Enter an InfluxQL query
> create database tesla
```

Additionally I suggest you to setup authentication or close the InfluxDB Port with a Packetfileter of your choice, if the Machine you use for Scraping has a Internetfacing Interface.

- Install Grafana as in http://docs.grafana.org/installation/debian/

- Get Grafana grafana-trackmap-panel

```
cd /var/lib/grafana/plugins
git clone https://github.com/pR0Ps/grafana-trackmap-panel
cd grafana-trackmap-panel
git checkout releases
```

- Get Grafana natel-discrete-panel

```
grafana-cli plugins install natel-discrete-panel
```

- Import the Dashboard JSON Files included in this repository.

**Note to the US-Users**: Since the API reports all Range Values in Miles, i included two dashboard variables to match your preferences. By default the Conversion to km / kph is done, to get rid of this go to the dashboard settings:

![Driving Dashboard](https://raw.githubusercontent.com/lephisto/tesla-apiscraper/master/screenshots/dashboardsetting_templatevar.png)

There you can change $rangeunit "km" to "mi" and $rangefactor 1.60934 to 1.0 and you're good to go.

## Install API Scraper

- Get API Scraper

```
git clone https://github.com/lephisto/tesla-apiscraper
```

- Get Python InfluxDB Module

```
pip install influxdb
```

- Configure API Scraper

```
cp config.py.dist config.py
vim config.py
```

Set Tesla and Influxdb Credentials there.

Afterwards start the Scraping:

```
python apiscraper.py
```

Once you know everything is running fine you can start the scraper to keep running with screen or tmux, or feel free to write down a systemd service definition file.

```
tmux new-session -s apiscraper 'python apiscraper.py'
```
## Known Limitations and issues

- If you narrow down Timefilter too much, and there are no Measurements, you won't see anything in the Graph and Discrete.
- The Code is far from being clean and in some way spaghetti'ish. This will be cleaned up in future Versions.
- Boolean Values from the API currently won't show

## Some remarks about the Owner APIScraper

- As stated below, the owner API is crafted for being used by the ios or android app. One challenge was to implement a reliable sleepmode. If the car is awake, the API keeps it awake, as long as requests occur. Once it falls asleep, parts of the API can be called to check the sleep state without waking up the car, however, when the scraper detects that the car doesn't change Values (not driving, not charging), it increases the Poll interval until the Car falls asleep. Once it's asleep it checks the sleepstate every Minute. This ensures, that the stats don't miss relevant portions of rides when the car was just woken up, an issue some other monitoring implementations suffer from.

## No

- Due to incoming inquiries: I won't host an Instance of this for you nor provide any extensive Setup Support. This is aimed at people who know what they're doing. If there are Issues, open a Github Issue.

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
