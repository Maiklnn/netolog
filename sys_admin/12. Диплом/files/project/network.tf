# Одна облачная сеть (VPC) на весь стенд.
# Подсети разделены по назначению:
#   * приватные — внутренний контур: веб-серверы и Elasticsearch. Публичных
#     адресов у этих ВМ нет, выход в интернет — только через NAT-шлюз;
#   * публичные — ресурсы, доступные из интернета: ВМ bastion, Zabbix, Kibana
#     и узлы L7-балансировщика.
resource "yandex_vpc_network" "develop" {
  name = "develop-fops-${var.flow}"
}

# ===== Приватные подсети: внутренний контур =====
# Выход в интернет — через NAT-шлюз (см. маршрутную таблицу ниже). Из интернета
# эти ВМ недоступны: трафик к ним приходит либо от узлов балансировщика, либо
# с bastion, и разрешён группами безопасности только на нужные порты.
resource "yandex_vpc_subnet" "private_a" {
  name           = "private-a-${var.flow}"
  description    = "Внутренний контур, зона A: веб-сервер web-a, Elasticsearch"
  zone           = "ru-central1-a"
  network_id     = yandex_vpc_network.develop.id
  v4_cidr_blocks = ["10.0.1.0/24"]
  route_table_id = yandex_vpc_route_table.rt.id
}

resource "yandex_vpc_subnet" "private_b" {
  name           = "private-b-${var.flow}"
  description    = "Внутренний контур, зона B: веб-сервер web-b"
  zone           = "ru-central1-b"
  network_id     = yandex_vpc_network.develop.id
  v4_cidr_blocks = ["10.0.2.0/24"]
  route_table_id = yandex_vpc_route_table.rt.id
}

# ===== Публичные подсети =====
# Здесь размещены узлы балансировщика, а в зоне A — ещё и ВМ с публичными
# адресами: bastion, Zabbix и Kibana.
#
# Маршрута по умолчанию в этих подсетях нет намеренно. По документации VPC
# доступ в интернет изнутри ВМ и доступ к ней через публичный IP-адрес возможны
# только тогда, когда в подсети отсутствует статический маршрут 0.0.0.0/0:
# иначе трафик уходит через NAT-шлюз, и публичный адрес перестаёт работать.
# Узлам балансировщика подсети без маршрута нужны по той же причине — они
# принимают трафик из интернета на свои публичные адреса.
resource "yandex_vpc_subnet" "public_a" {
  name           = "public-a-${var.flow}"
  description    = "Публичная подсеть, зона A: bastion, Zabbix, Kibana, узлы балансировщика"
  zone           = "ru-central1-a"
  network_id     = yandex_vpc_network.develop.id
  v4_cidr_blocks = ["10.0.3.0/24"]
}

resource "yandex_vpc_subnet" "public_b" {
  name           = "public-b-${var.flow}"
  description    = "Публичная подсеть, зона B: узлы балансировщика"
  zone           = "ru-central1-b"
  network_id     = yandex_vpc_network.develop.id
  v4_cidr_blocks = ["10.0.4.0/24"]
}

#Квота статических публичных адресов в каталоге — 2, и оба уже заняты:
#адрес bastion (bastion-address-24-01) и адрес слушателей балансировщика
#(alb-address-24-01, см. alb.tf). Zabbix и Kibana получают динамические
#публичные адреса (nat = true без указания адреса) — они не расходуют квоту
#статических адресов. Входящий трафик на эти ВМ закрыт группами безопасности:
#доступ к их веб-интерфейсам есть только через слушатели балансировщика.

#создаем NAT для выхода в интернет
resource "yandex_vpc_gateway" "nat_gateway" {
  name = "fops-gateway-${var.flow}"
  shared_egress_gateway {}
}

#создаем сетевой маршрут для выхода в интернет через NAT
resource "yandex_vpc_route_table" "rt" {
  name       = "fops-route-table-${var.flow}"
  network_id = yandex_vpc_network.develop.id

  static_route {
    destination_prefix = "0.0.0.0/0"
    gateway_id         = yandex_vpc_gateway.nat_gateway.id
  }
}

# ===== Группы безопасности (firewall) =====
#
# Правило для всех групп: входящий трафик разрешён только к нужным портам и
# только из тех подсетей, откуда он действительно приходит. Исходящий трафик
# не ограничиваем (egress ANY) — ВМ обращаются к репозиториям пакетов, к
# NAT-шлюзу и друг к другу.
#
# Общие адреса подсетей:
#   10.0.1.0/24 — private-a  (web-a, Elasticsearch)
#   10.0.2.0/24 — private-b  (web-b)
#   10.0.3.0/24 — public-a   (bastion, Zabbix, Kibana, узлы балансировщика)
#   10.0.4.0/24 — public-b   (узлы балансировщика)
#
# Порт 10050 (агент Zabbix) открыт во всех группах ВМ, где стоит агент:
# сервер опрашивает агентов напрямую, а из публичной подсети public-a
# (10.0.3.0/24) приходит и сам опрос, и активные проверки агентов.

# Bastion host (jump host). Единственная ВМ, открытая в интернет, и на ней
# открыт ровно один порт — SSH. Через неё Ansible подключается к ВМ внутреннего
# контура (ProxyCommand в inventory), сама она внутрь ходит по SSH.
resource "yandex_vpc_security_group" "bastion" {
  name       = "bastion-sg-${var.flow}"
  network_id = yandex_vpc_network.develop.id

  ingress {
    description    = "SSH из интернета — единственный открытый порт"
    protocol       = "TCP"
    v4_cidr_blocks = ["0.0.0.0/0"]
    port           = 22
  }
  ingress {
    description    = "Zabbix-агент: опрос с Zabbix-сервера"
    protocol       = "TCP"
    port           = 10050
    v4_cidr_blocks = ["10.0.3.0/24"]
  }
  egress {
    description    = "Permit ANY"
    protocol       = "ANY"
    v4_cidr_blocks = ["0.0.0.0/0"]
    from_port      = 0
    to_port        = 65535
  }
}

# Веб-серверы (web-a, web-b). Наружу не смотрят вообще: HTTP-трафик приходит
# только от узлов балансировщика, SSH — только с bastion.
resource "yandex_vpc_security_group" "web_sg" {
  name       = "web-sg-${var.flow}"
  network_id = yandex_vpc_network.develop.id

  ingress {
    description    = "HTTP от узлов балансировщика"
    protocol       = "TCP"
    port           = 80
    v4_cidr_blocks = ["10.0.3.0/24", "10.0.4.0/24"]
  }
  ingress {
    description    = "HTTPS от узлов балансировщика"
    protocol       = "TCP"
    port           = 443
    v4_cidr_blocks = ["10.0.3.0/24", "10.0.4.0/24"]
  }
  ingress {
    description    = "SSH с bastion"
    protocol       = "TCP"
    port           = 22
    v4_cidr_blocks = ["10.0.3.0/24"]
  }
  ingress {
    description    = "Zabbix-агент: опрос с Zabbix-сервера"
    protocol       = "TCP"
    port           = 10050
    v4_cidr_blocks = ["10.0.3.0/24"]
  }
  egress {
    description    = "Permit ANY"
    protocol       = "ANY"
    v4_cidr_blocks = ["0.0.0.0/0"]
    from_port      = 0
    to_port        = 65535
  }
}

# Zabbix-сервер. Публичный адрес есть (для установки пакетов), но входящий
# трафик на него открыт только с агентов (10051) и от узлов балансировщика (80,
# веб-интерфейс публикуется слушателем 8080). SSH — с bastion.
resource "yandex_vpc_security_group" "zabbix" {
  name       = "zabbix-sg-${var.flow}"
  network_id = yandex_vpc_network.develop.id

  ingress {
    description    = "Агенты присылают метрики (веб-серверы, Elasticsearch, Kibana, bastion)"
    protocol       = "TCP"
    port           = 10051
    v4_cidr_blocks = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  }
  ingress {
    description    = "Веб-интерфейс Zabbix от узлов балансировщика"
    protocol       = "TCP"
    port           = 80
    v4_cidr_blocks = ["10.0.3.0/24", "10.0.4.0/24"]
  }
  ingress {
    description    = "SSH с bastion"
    protocol       = "TCP"
    port           = 22
    v4_cidr_blocks = ["10.0.3.0/24"]
  }
  ingress {
    description    = "Zabbix-агент: опрос с Zabbix-сервера"
    protocol       = "TCP"
    port           = 10050
    v4_cidr_blocks = ["10.0.3.0/24"]
  }
  egress {
    description    = "Permit ANY"
    protocol       = "ANY"
    v4_cidr_blocks = ["0.0.0.0/0"]
    from_port      = 0
    to_port        = 65535
  }
}

# ВМ ELK (Elasticsearch, Kibana):
#   9200 — Elasticsearch: журналы присылает Filebeat с веб-серверов, запросы
#          выполняет Kibana. Наружу не публикуется;
#   5601 — Kibana: веб-интерфейс от узлов балансировщика, а также запросы
#          от веб-серверов — команда filebeat setup загружает через Kibana
#          дашборды по журналам nginx;
#   22   — SSH с bastion;
#   10050 — агент Zabbix: сервер опрашивает его напрямую (пассивные проверки).
#          Порт нужен в каждой группе безопасности, иначе после отказа от
#          «разрешающей всё внутри VPC» группы LAN-sg агенты перестают отвечать.
resource "yandex_vpc_security_group" "elk" {
  name       = "elk-sg-${var.flow}"
  network_id = yandex_vpc_network.develop.id

  ingress {
    description    = "Elasticsearch API от веб-серверов и Kibana"
    protocol       = "TCP"
    port           = 9200
    v4_cidr_blocks = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  }
  ingress {
    description    = "Kibana: веб-интерфейс от узлов балансировщика и setup от веб-серверов"
    protocol       = "TCP"
    port           = 5601
    v4_cidr_blocks = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24", "10.0.4.0/24"]
  }
  ingress {
    description    = "SSH с bastion"
    protocol       = "TCP"
    port           = 22
    v4_cidr_blocks = ["10.0.3.0/24"]
  }
  ingress {
    description    = "Zabbix-агент: опрос с Zabbix-сервера"
    protocol       = "TCP"
    port           = 10050
    v4_cidr_blocks = ["10.0.3.0/24"]
  }
  egress {
    description    = "Permit ANY"
    protocol       = "ANY"
    v4_cidr_blocks = ["0.0.0.0/0"]
    from_port      = 0
    to_port        = 65535
  }
}

resource "yandex_vpc_security_group" "alb" {
  name       = "alb-sg-${var.flow}"
  network_id = yandex_vpc_network.develop.id

  # входящий трафик от пользователей на порт слушателя
  ingress {
    description    = "Allow HTTP from internet"
    protocol       = "TCP"
    port           = 80
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  # входящий трафик от пользователей на порт второго слушателя
  # (веб-интерфейс Zabbix)
  ingress {
    description    = "Allow Zabbix UI from internet"
    protocol       = "TCP"
    port           = 8080
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  # входящий трафик от пользователей на порт третьего слушателя
  # (веб-интерфейс Kibana)
  ingress {
    description    = "Allow Kibana UI from internet"
    protocol       = "TCP"
    port           = 5601
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  # проверки состояния узлов балансировщика между зонами доступности
  ingress {
    description       = "Allow balancer healthchecks"
    protocol          = "TCP"
    port              = 30080
    predefined_target = "loadbalancer_healthchecks"
  }

  # исходящий трафик на целевые ВМ из целевой группы
  egress {
    description    = "Permit ANY to backend VMs"
    protocol       = "ANY"
    v4_cidr_blocks = ["0.0.0.0/0"]
    from_port      = 0
    to_port        = 65535
  }
}
