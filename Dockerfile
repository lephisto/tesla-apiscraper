FROM debian:stretch-slim

RUN apt-get -y update

# Install Python
RUN apt-get -y install python
RUN apt-get -y install apt-transport-https
RUN apt-get -y install curl
RUN apt-get -y install gnupg2

# Install Influx
RUN curl -sL https://repos.influxdata.com/influxdb.key | apt-key add -
RUN echo "deb https://repos.influxdata.com/debian stretch stable" | tee /etc/apt/sources.list.d/influxdb.list
RUN apt-get -y update
RUN apt-get -y install influxdb

# Install Grafana
RUN curl https://packages.grafana.com/gpg.key | apt-key add -
RUN echo "deb https://packages.grafana.com/oss/deb stable main" | tee /etc/apt/sources.list.d/grafana.list
RUN apt-get -y update
RUN apt-get -y install grafana

# Install Grafana addons
RUN apt-get -y install git
WORKDIR /var/lib/grafana/plugins
RUN git clone https://github.com/pR0Ps/grafana-trackmap-panel
WORKDIR /var/lib/grafana/plugins/grafana-trackmap-panel
RUN git checkout releases
RUN grafana-cli plugins install natel-discrete-panel

# Install Tesla API Scraper
RUN apt-get -y install python-pip
WORKDIR /
RUN git clone https://github.com/freerobby/tesla-apiscraper
RUN pip install influxdb

# Configure it
WORKDIR tesla-apiscraper
RUN cp config.py.dist config.py
RUN service influxdb start && \
  influx -execute "create database tesla" && \
  service influxdb stop

# Create temp files for dashboard API calls
RUN echo '{"dashboard":' > /tmp/Charging.json
RUN echo '{"dashboard":' > /tmp/Climate.json
RUN echo '{"dashboard":' > /tmp/Driving.json
RUN cat ./grafana-dashboards/Charging.json >> /tmp/Charging.json
RUN cat ./grafana-dashboards/Climate.json >> /tmp/Climate.json
RUN cat ./grafana-dashboards/Driving.json >> /tmp/Driving.json
RUN echo '}' >> /tmp/Charging.json
RUN echo '}' >> /tmp/Climate.json
RUN echo '}' >> /tmp/Driving.json
RUN sed -i 's/\${DS_TESLA}/InfluxDB/g' /tmp/Charging.json
RUN sed -i 's/\${DS_TESLA}/InfluxDB/g' /tmp/Climate.json
RUN sed -i 's/\${DS_TESLA}/InfluxDB/g' /tmp/Driving.json

# Install Grafana data source and dashboards
RUN service influxdb start && \
  service grafana-server start ; sleep 5 && \
  curl -v -H 'Content-Type: application/json' -d @./grafana-datasources/influxdb.json http://admin:admin@localhost:3000/api/datasources && \
  curl -v -H 'Content-Type: application/json' -d @/tmp/Charging.json http://admin:admin@localhost:3000/api/dashboards/db && \
  curl -v -H 'Content-Type: application/json' -d @/tmp/Climate.json http://admin:admin@localhost:3000/api/dashboards/db && \
  curl -v -H 'Content-Type: application/json' -d @/tmp/Driving.json http://admin:admin@localhost:3000/api/dashboards/db && \
  service grafana-server stop && \
  service influxdb stop

RUN sed -i "s/a_influxpass = '<influxdbpassword>'/a_influxpass = None/g" /tesla-apiscraper/config.py
RUN sed -i "s/a_influxuser = 'tesla'/a_influxuser = None/g" /tesla-apiscraper/config.py

# Define our startup script
RUN echo "#!/bin/bash" > /start.sh
RUN echo "sed -i \"s/<email>/\${TESLA_USERNAME}/g\" /tesla-apiscraper/config.py" >> /start.sh
RUN echo "sed -i \"s/<password>/\${TESLA_PASSWORD}/g\" /tesla-apiscraper/config.py" >> /start.sh
RUN echo "service influxdb start" >> /start.sh
RUN echo "service grafana-server start" >> /start.sh
RUN echo "python /tesla-apiscraper/apiscraper.py" >> /start.sh
RUN chmod +x /start.sh

# Run it
EXPOSE 3000
CMD /start.sh