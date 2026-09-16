output "bastion_public_ip" {
  description = "Публичный IP bastion-сервера (точка входа для SSH)"
  value       = yandex_compute_instance.bastion.network_interface.0.nat_ip_address
}

output "web_internal_ips" {
  description = "Внутренние IP веб-серверов"
  value = {
    web_a = yandex_compute_instance.web_a.network_interface.0.ip_address
    web_b = yandex_compute_instance.web_b.network_interface.0.ip_address
  }
}

output "zabbix_internal_ip" {
  description = "Внутренний IP ВМ с Zabbix-сервером"
  value       = yandex_compute_instance.zabbix.network_interface.0.ip_address
}

output "elasticsearch_internal_ip" {
  description = "Внутренний IP ВМ с Elasticsearch (приём журналов nginx)"
  value       = yandex_compute_instance.elasticsearch.network_interface.0.ip_address
}

output "kibana_internal_ip" {
  description = "Внутренний IP ВМ с Kibana"
  value       = yandex_compute_instance.kibana.network_interface.0.ip_address
}

output "alb_zabbix_public_ip" {
  description = "Публичный IP слушателя Zabbix (порт 8080) — адрес веб-интерфейса"
  value = try(
    [for l in yandex_alb_load_balancer.web_alb.listener : l
      if l.name == "zabbix-listener"][0].endpoint[0].address[0].external_ipv4_address[0].address,
    null
  )
}

output "alb_kibana_public_ip" {
  description = "Публичный IP слушателя Kibana (порт 5601) — адрес веб-интерфейса"
  value = try(
    [for l in yandex_alb_load_balancer.web_alb.listener : l
      if l.name == "kibana-listener"][0].endpoint[0].address[0].external_ipv4_address[0].address,
    null
  )
}

output "alb_public_ip" {
  description = "Публичный IP балансировщика — адрес, по которому открывается сайт"
  # адрес статический (yandex_vpc_address.alb), но на этапе plan ресурса может ещё не быть
  value = try(
    yandex_alb_load_balancer.web_alb.listener[0].endpoint[0].address[0].external_ipv4_address[0].address,
    null
  )
}
