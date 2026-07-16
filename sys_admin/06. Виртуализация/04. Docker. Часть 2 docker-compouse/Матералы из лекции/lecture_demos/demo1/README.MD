том   -v ./custom.ini:/etc/grafana/grafana.ini 
заменить в контейнере /etc/grafana/grafana.ini на custom.ini котроый находися в корне папки 
       

удаление всех запущенных контейнеров
    docker rm -v -f $(docker ps -qa) 

создание сети
    docker network create prometheus-stack && docker network ls

запускаем контейнер node-exporter
    docker run -d \
      --net="host" \
      --name node_exporter \
      -v "/:/host:ro,rslave" \
      quay.io/prometheus/node-exporter:latest \
      --path.rootfs=/host

запускаем контейнер node-exporter
    docker run -d \
      --net="host" \
      --name pushgateway \
      prom/pushgateway

запускаем контейнер alertmanager
    docker run -d \
      --net="host" \
      --name alertmanager \
      quay.io/prometheus/alertmanager

запускаем контейнер prometheus
    docker run -d \
      --net="host" \
      -v ./prometheus.yml:/etc/prometheus/prometheus.yml \
      -v ./alert_rules.yml:/etc/prometheus/alert_rules.yml \
      --name prometheus \
      prom/prometheus

запускаем контейнер grafana
    docker run -d \
      --net="host" \
      --name=grafana \
      -v ./custom.ini:/etc/grafana/grafana.ini \  
      grafana/grafana:11.5.0


ss -tlpn
curl http://127.0.0.1:9100/metrics
curl http://127.0.0.1:9091/metrics

docker restart prometheus
docker rm -f $(docker ps -a -q)

Для изучения YAML:
https://grafana.com/grafana/dashboards/1860-node-exporter-full/
https://www.yamllint.com/
https://guifier.com/yaml
https://github.com/samber/awesome-prometheus-alerts
https://github.com/adavesik/compoviz
https://github.com/maliknajjar/guifier/blob/main/docker-compose.yml

docker container rm -f prometheus && docker container rm -f node_exporter && docker container rm -f pushgateway && docker container rm -f grafana && docker container rm -f alertmanager
