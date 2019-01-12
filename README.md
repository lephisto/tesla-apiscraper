## tesla-apiscraper
API Scraper for pulling Vehicle Statistics from the Tesla Owner API into an InfluxDB + Grafana Dashboards

#Install Dependencies:

- Install Python

eg:
```
sudo apt install python
```


- Install InfluxDB as in https://docs.influxdata.com/influxdb/v1.7/introduction/installation/

Additionally I suggest you to setup authentication or close the InfluxDB Port with a Packetfileter of your choice, if the Machine you use for Scraping has a Internetfacing Interface.

- Install Grafana  as in http://docs.grafana.org/installation/debian/


# Install API Scraper

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

python apiscraper.py

Once you know everything is running fine you can start the Scraper to keep running with Screen or tmux, or even write a systemd service.

```
tmux new-session -s apiscraper 'python apiscraper.py'
```
