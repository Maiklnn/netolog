# Целевая группа: обе веб-ВМ во внутренней сети (внешних адресов у них нет)
resource "yandex_alb_target_group" "web_tg" {
  name = "web-tg-${var.flow}"

  target {
    subnet_id  = yandex_vpc_subnet.private_a.id
    ip_address = yandex_compute_instance.web_a.network_interface.0.ip_address
  }

  target {
    subnet_id  = yandex_vpc_subnet.private_b.id
    ip_address = yandex_compute_instance.web_b.network_interface.0.ip_address
  }
}

# Группа бэкендов: HTTP на 80-й порт, проверка работоспособности по пути "/"
resource "yandex_alb_backend_group" "web_bg" {
  name = "web-bg-${var.flow}"

  http_backend {
    name             = "web-backend"
    weight           = 1
    port             = 80
    target_group_ids = [yandex_alb_target_group.web_tg.id]

    healthcheck {
      timeout  = "1s"
      interval = "2s"
      http_healthcheck {
        path = "/"
      }
    }
  }
}

# HTTP-роутер
resource "yandex_alb_http_router" "web_router" {
  name = "web-router-${var.flow}"
}

# Виртуальный хост: весь путь "/" уходит на группу бэкендов
resource "yandex_alb_virtual_host" "web_vh" {
  name           = "web-vh-${var.flow}"
  http_router_id = yandex_alb_http_router.web_router.id

  route {
    name = "web-route"

    http_route {
      http_match {
        path {
          prefix = "/"
        }
      }
      http_route_action {
        backend_group_id = yandex_alb_backend_group.web_bg.id
      }
    }
  }
}

# Статический публичный адрес балансировщика. Выделяем его в зоне ru-central1-a —
# той же, где расположены ресурсные единицы балансировщика (см. allocation_policy
# ниже). Автоматически выделенный адрес попадал в зону ru-central1-d и работал не из
# всех внешних сетей: с сети заказчика SYN до балансировщика не доходил вообще
# (в метриках — ноль соединений), при этом ICMP до этого адреса проходил, а порт 80
# до других адресов Yandex Cloud с той же сети открывался нормально. Плюс статический
# адрес не меняется при пересоздании балансировщика и его можно проверить заранее.
resource "yandex_vpc_address" "alb" {
  name = "alb-address-${var.flow}"

  # иначе адрес нельзя будет удалить вместе с остальной инфраструктурой
  deletion_protection = false

  external_ipv4_address {
    zone_id = "ru-central1-a"
  }
}

# L7-балансировщик: узлы в двух зонах, три слушателя на одном статическом публичном
# адресе из yandex_vpc_address — HTTP:80 (сайт), HTTP:8080 (Zabbix), HTTP:5601 (Kibana)
resource "yandex_alb_load_balancer" "web_alb" {
  name       = "web-alb-${var.flow}"
  network_id = yandex_vpc_network.develop.id

  # Только группа балансировщика. Другие группы сюда добавлять нельзя: трафик
  # должен быть разрешён всеми группами, назначенными ресурсу, поэтому любая
  # группа с узкими входящими правилами (например, доступ к 80 только из
  # внутренних подсетей) отсечёт внешних клиентов.
  security_group_ids = [yandex_vpc_security_group.alb.id]

  # Узлы балансировщика размещаем в публичных подсетях — по одному на зону
  # доступности (public-a и public-b). Маршрута по умолчанию в них нет: узлы
  # принимают трафик из интернета на свои публичные адреса, а с маршрутом
  # 0.0.0.0/0 трафик уходил бы через NAT-шлюз.
  allocation_policy {
    location {
      zone_id   = "ru-central1-a"
      subnet_id = yandex_vpc_subnet.public_a.id
    }
    location {
      zone_id   = "ru-central1-b"
      subnet_id = yandex_vpc_subnet.public_b.id
    }
  }

  listener {
    name = "http-listener"

    endpoint {
      # адрес статический — тот же, что и у остальных слушателей
      address {
        external_ipv4_address {
          address = yandex_vpc_address.alb.external_ipv4_address[0].address
        }
      }
      ports = [80]
    }

    http {
      handler {
        http_router_id = yandex_alb_http_router.web_router.id
      }
    }
  }

  # Второй слушатель — веб-интерфейс Zabbix на порту 8080 того же публичного
  # адреса (тот же yandex_vpc_address, что и у первого слушателя). Все слушатели
  # объявлены inline: смешивать inline-слушатели и отдельный ресурс
  # yandex_alb_listener нельзя — при обновлении балансировщика отдельный
  # слушатель будет удалён. Кроме того, провайдер не принимает пустой блок
  # external_ipv4_address {} у НОВОГО слушателя при обновлении
  # («Either external ipv4 address ... should be specified») — поэтому адрес
  # указываем явно.
  listener {
    name = "zabbix-listener"

    endpoint {
      address {
        external_ipv4_address {
          address = yandex_vpc_address.alb.external_ipv4_address[0].address
        }
      }
      ports = [8080]
    }

    http {
      handler {
        http_router_id = yandex_alb_http_router.zabbix_router.id
      }
    }
  }

  # Третий слушатель — веб-интерфейс Kibana на порту 5601 того же публичного
  # адреса. ВМ Kibana внешнего адреса не имеет, поэтому в интернет её публикует
  # балансировщик; группа безопасности разрешает 5601 на узлах балансировщика
  # только от узлов ALB (см. elk-sg в network.tf).
  listener {
    name = "kibana-listener"

    endpoint {
      address {
        external_ipv4_address {
          address = yandex_vpc_address.alb.external_ipv4_address[0].address
        }
      }
      ports = [5601]
    }

    http {
      handler {
        http_router_id = yandex_alb_http_router.kibana_router.id
      }
    }
  }
}

# ===== Zabbix: доступ к веб-интерфейсу через отдельный слушатель 8080 =====

# Целевая группа из одной ВМ — Zabbix-сервер
resource "yandex_alb_target_group" "zabbix_tg" {
  name = "zabbix-tg-${var.flow}"

  target {
    subnet_id  = yandex_vpc_subnet.public_a.id
    ip_address = yandex_compute_instance.zabbix.network_interface.0.ip_address
  }
}

# Группа бэкендов Zabbix: HTTP на порт 80 ВМ (nginx с фронтендом Zabbix)
resource "yandex_alb_backend_group" "zabbix_bg" {
  name = "zabbix-bg-${var.flow}"

  http_backend {
    name             = "zabbix-backend"
    weight           = 1
    port             = 80
    target_group_ids = [yandex_alb_target_group.zabbix_tg.id]

    healthcheck {
      timeout  = "1s"
      interval = "2s"
      http_healthcheck {
        path = "/"
      }
    }
  }
}

# Отдельный HTTP-роутер для Zabbix: в нём виртуальный хост по умолчанию,
# поэтому Host-заголовок не нужен — интерфейс открывается прямо по IP:8080
resource "yandex_alb_http_router" "zabbix_router" {
  name = "zabbix-router-${var.flow}"
}

resource "yandex_alb_virtual_host" "zabbix_vh" {
  name           = "zabbix-vh-${var.flow}"
  http_router_id = yandex_alb_http_router.zabbix_router.id

  route {
    name = "zabbix-route"

    http_route {
      http_match {
        path {
          prefix = "/"
        }
      }
      http_route_action {
        backend_group_id = yandex_alb_backend_group.zabbix_bg.id
      }
    }
  }
}

# ===== Kibana: доступ к веб-интерфейсу через слушатель 5601 =====

# Целевая группа из одной ВМ — Kibana
resource "yandex_alb_target_group" "kibana_tg" {
  name = "kibana-tg-${var.flow}"

  target {
    subnet_id  = yandex_vpc_subnet.public_a.id
    ip_address = yandex_compute_instance.kibana.network_interface.0.ip_address
  }
}

# Группа бэкендов Kibana: HTTP на порт 5601 ВМ (Kibana слушает его же).
# Проверка работоспособности — по пути /api/status: там Kibana отдаёт 200 и JSON
# о своём состоянии. Путь "/" для проверки не годится: Kibana отвечает на него
# редиректом на /app/home, и узел не считается работоспособным.
resource "yandex_alb_backend_group" "kibana_bg" {
  name = "kibana-bg-${var.flow}"

  http_backend {
    name             = "kibana-backend"
    weight           = 1
    port             = 5601
    target_group_ids = [yandex_alb_target_group.kibana_tg.id]

    healthcheck {
      timeout  = "2s"
      interval = "5s"
      http_healthcheck {
        path = "/api/status"
      }
    }
  }
}

# Отдельный HTTP-роутер для Kibana (виртуальный хост по умолчанию, Host не нужен)
resource "yandex_alb_http_router" "kibana_router" {
  name = "kibana-router-${var.flow}"
}

resource "yandex_alb_virtual_host" "kibana_vh" {
  name           = "kibana-vh-${var.flow}"
  http_router_id = yandex_alb_http_router.kibana_router.id

  route {
    name = "kibana-route"

    http_route {
      http_match {
        path {
          prefix = "/"
        }
      }
      http_route_action {
        backend_group_id = yandex_alb_backend_group.kibana_bg.id
      }
    }
  }
}
