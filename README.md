# tesla-apiscraper
Selfhosted API Scraper for pulling Vehicle Statistics from the Tesla Owner API into an InfluxDB visualisation on Grafana Dashboards.

**Putting an end to __handing out the Key__ for your 100+ Grand Car to a third party you don't know.**

This can be hosted on any System that's capable of running InfluxDB, Grafana and Python. In this short Guide I assume you're using a Debian'ish Operating System. It can run on a dedicated Linux Server out there on the Internets or on your Home Raspberry Pi.

## Screenshots

![Driving Dashboard](https://raw.githubusercontent.com/lephisto/tesla-apiscraper/master/screenshots/driving_dash.png)

![Charging Dashboard](https://raw.githubusercontent.com/lephisto/tesla-apiscraper/master/screenshots/charging_dash.png)

## Installation:

- Install Python

eg:
```
sudo apt install python
```


- Install InfluxDB as in https://docs.influxdata.com/influxdb/v1.7/introduction/installation/

Additionally I suggest you to setup authentication or close the InfluxDB Port with a Packetfileter of your choice, if the Machine you use for Scraping has a Internetfacing Interface.

- Install Grafana as in http://docs.grafana.org/installation/debian/ and import the Dashboard JSON Files included in this repository.

- Install two required Grafana Panels:

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


## Install API Scraper

- Get API Scraper

```
git clone https://github.com/lephisto/tesla-apiscraper
```

- Get TeslaJSON Python Module

```
wget https://github.com/gglockner/teslajson/archive/master.zip
unzip master.zip
cp teslajson-master/teslajson.py .
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

Once you know everything is running fine you can start the Scraper to keep running with Screen or tmux, or feel free to write down a systemd service file.

```
tmux new-session -s apiscraper 'python apiscraper.py'
```
## Known Limitations and issues

- If you narrow down Timefilter too much, and there are no Measurements, you won't see anything in the Graph and Discrete.
- The Code is far from being clean and in some way spaghetti'ish. This will be cleaned up in future Versions.

## No

- Due to incoming inquiries: I won't host an Instance of this for you nor provide any extensive Setup Support. This is aimed at people who know what they're doing. If there are Issues, open a Github Issue.

## More Disclaimer

- Please note that the use of the Tesla REST API in general and the use of this software in particular is not endorsed by Tesla. You use this software at your own risk. The author does not take responsibility for anything related to the use of this software.

## To Do's

- Multithreaded Stat pulling
- Code Cleanup
