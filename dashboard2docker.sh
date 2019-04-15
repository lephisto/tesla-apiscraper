#!/bin/bash
cp grafana-dashboards/TeslaMetricsV2.json provisioning/dashboards/TeslaMetricsV2.json
sed -i 's/${DS_TESLA}/Tesla/g' provisioning/dashboards/*.json
