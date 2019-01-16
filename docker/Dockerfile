FROM ubuntu:18.04

ARG DATA_PATH

RUN apt-get -y update && apt-get -y install python python-pip
RUN pip install influxdb

WORKDIR ${DATA_PATH}/tesla-apiscraper
CMD python apiscraper.py
