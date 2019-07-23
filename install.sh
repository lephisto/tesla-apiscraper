#!/bin/bash

teslaEmail=$1
teslaPassword=$2

if [[ $teslaEmail == "" || $teslaPassword == "" ]]; then 
    echo "Please enter your email and password"
    exit
fi

device=$(cat /proc/device-tree/model)
if [[ $device == *"Raspberry Pi Zero"* ]]; then 
    echo "This will not work on a Pi Zero, quitting install"
    exit
fi

git clone https://github.com/Lunars/tesla-apiscraper.git
cd tesla-apiscraper

# Create the config file
cp config.py.compose config.py
sed -i "s/<email>/${teslaEmail}/g" ./config.py
sed -i "s/<password>/${teslaPassword}/g" ./config.py

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