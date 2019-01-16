#!/bin/bash

export DATA_PATH=/data
export BASEDIR=${PWD}

if [[ ! $(docker --version) ]]; then
  echo "docker is not installed"
  exit 1
fi

if [[ ! $(docker-compose --version) ]]; then
  echo "docker is not installed"
  exit 1
fi

if [[ ! -f ../config.py ]]; then
  echo "please setup your config.py file"
  exit 1
fi

if [[ ! -d ${DATA_PATH}/grafana/plugins/grafana-trackmap-panel ]]; then
  mkdir -p ${DATA_PATH}/grafana/plugins
  cd ${DATA_PATH}/grafana/plugins/
  git clone https://github.com/pR0Ps/grafana-trackmap-panel
  cd ${DATA_PATH}/grafana/plugins/grafana-trackmap-panel
  git checkout releases
  chown -R 472:472 ${DATA_PATH}/grafana
fi

cd ${BASEDIR}
docker-compose build --build-arg DATA_PATH=${DATA_PATH} apiscraper
docker-compose up
