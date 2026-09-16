
#считываем данные об образе ОС
data "yandex_compute_image" "ubuntu_2204_lts" {
  family = "ubuntu-2204-lts"
}

#Конфигурация всех ВМ одинаковая (см. var.test): 2 ядра, 20% Intel Ice Lake,
#2 ГБ памяти, диск 10 ГБ network-hdd. platform_id = standard-v3 — это Intel Ice Lake.
#preemptible задаётся переменной: перед сдачей работы переключить на false.
#Исключение — ВМ ELK: у Elasticsearch 4 ГБ памяти и диск 20 ГБ (см. var.elasticsearch).
#
#Размещение ВМ по подсетям (см. network.tf):
#  * приватные (private-a, private-b) — внутренний контур: web-a, web-b,
#    Elasticsearch. Публичных адресов нет, выход в интернет через NAT-шлюз;
#  * публичная (public-a) — bastion, Zabbix, Kibana и узлы балансировщика.
#    У bastion адрес статический, у Zabbix и Kibana — динамические публичные
#    адреса (нужны только для установки пакетов), входящий трафик закрыт
#    группами безопасности.

#Статический публичный адрес для bastion. Без него адрес меняется при каждой
#остановке ВМ (а ВМ останавливается при изменении resources/scheduling_policy),
#и ProxyCommand в inventory ломается.
resource "yandex_vpc_address" "bastion" {
  name = "bastion-address-${var.flow}"

  external_ipv4_address {
    zone_id = "ru-central1-a"
  }
}

#Bastion host (jump host): единственная ВМ, доступная из интернета, и на ней
#открыт ровно один порт — SSH. Стоит в публичной подсети public-a; именно через
#неё Ansible подключается к ВМ внутреннего контура (ProxyCommand в inventory).
resource "yandex_compute_instance" "bastion" {
  name        = "bastion" #Имя ВМ в облачной консоли
  hostname    = "bastion" #формирует FDQN имя хоста, без hostname будет сгенрировано случаное имя.
  platform_id = "standard-v3"
  #разрешает останавливать ВМ при изменении resources / scheduling_policy
  allow_stopping_for_update = true
  zone                      = "ru-central1-a" #зона ВМ должна совпадать с зоной subnet!!!

  resources {
    cores         = var.test.cores
    memory        = var.test.memory
    core_fraction = var.test.core_fraction
  }

  boot_disk {
    initialize_params {
      image_id = data.yandex_compute_image.ubuntu_2204_lts.image_id
      type     = "network-hdd"
      size     = 10
    }
  }

  metadata = {
    user-data          = file("./cloud-init.yml")
    serial-port-enable = 1
  }

  scheduling_policy { preemptible = var.preemptible }

  network_interface {
    subnet_id          = yandex_vpc_subnet.public_a.id #публичная подсеть: bastion — точка входа извне
    nat                = true
    nat_ip_address     = yandex_vpc_address.bastion.external_ipv4_address[0].address
    security_group_ids = [yandex_vpc_security_group.bastion.id]
  }
}


resource "yandex_compute_instance" "web_a" {
  name        = "web-a" #Имя ВМ в облачной консоли
  hostname    = "web-a" #формирует FDQN имя хоста, без hostname будет сгенрировано случаное имя.
  platform_id = "standard-v3"
  #разрешает останавливать ВМ при изменении resources / scheduling_policy
  allow_stopping_for_update = true
  zone                      = "ru-central1-a" #зона ВМ должна совпадать с зоной subnet!!!


  resources {
    cores         = var.test.cores
    memory        = var.test.memory
    core_fraction = var.test.core_fraction
  }

  boot_disk {
    initialize_params {
      image_id = data.yandex_compute_image.ubuntu_2204_lts.image_id
      type     = "network-hdd"
      size     = 10
    }
  }

  metadata = {
    user-data          = file("./cloud-init.yml")
    serial-port-enable = 1
  }

  scheduling_policy { preemptible = var.preemptible }

  network_interface {
    subnet_id          = yandex_vpc_subnet.private_a.id
    nat                = false #внешнего IP нет, доступ только через балансировщик и bastion
    security_group_ids = [yandex_vpc_security_group.web_sg.id]
  }
}

resource "yandex_compute_instance" "web_b" {
  name        = "web-b" #Имя ВМ в облачной консоли
  hostname    = "web-b" #формирует FDQN имя хоста, без hostname будет сгенрировано случаное имя.
  platform_id = "standard-v3"
  #разрешает останавливать ВМ при изменении resources / scheduling_policy
  allow_stopping_for_update = true
  zone                      = "ru-central1-b" #зона ВМ должна совпадать с зоной subnet!!!

  resources {
    cores         = var.test.cores
    memory        = var.test.memory
    core_fraction = var.test.core_fraction
  }

  boot_disk {
    initialize_params {
      image_id = data.yandex_compute_image.ubuntu_2204_lts.image_id
      type     = "network-hdd"
      size     = 10
    }
  }

  metadata = {
    user-data          = file("./cloud-init.yml")
    serial-port-enable = 1
  }

  scheduling_policy { preemptible = var.preemptible }

  network_interface {
    subnet_id          = yandex_vpc_subnet.private_b.id
    nat                = false #внешнего IP нет, доступ только через балансировщик и bastion
    security_group_ids = [yandex_vpc_security_group.web_sg.id]

  }
}

#ВМ с Zabbix-сервером: хранит историю метрик со всех ВМ.
#Размещена в публичной подсети public-a вместе с bastion и Kibana. Публичный
#адрес у ВМ динамический и нужен только для установки пакетов: маршрута по
#умолчанию в публичной подсети нет. Веб-интерфейс доступен через балансировщик
#(listener 8080), SSH — через bastion. Конфигурация минимальная, как у остальных ВМ.
resource "yandex_compute_instance" "zabbix" {
  name                      = "zabbix" #Имя ВМ в облачной консоли
  hostname                  = "zabbix" #формирует FDQN имя хоста
  platform_id               = "standard-v3"
  allow_stopping_for_update = true
  zone                      = "ru-central1-a"

  resources {
    cores         = var.test.cores
    memory        = var.test.memory
    core_fraction = var.test.core_fraction
  }

  boot_disk {
    initialize_params {
      image_id = data.yandex_compute_image.ubuntu_2204_lts.image_id
      type     = "network-hdd"
      size     = 10
    }
  }

  metadata = {
    user-data          = file("./cloud-init.yml")
    serial-port-enable = 1
  }

  scheduling_policy { preemptible = var.preemptible }

  network_interface {
    subnet_id = yandex_vpc_subnet.public_a.id
    # публичная подсеть: маршрута по умолчанию в ней нет, поэтому динамический
    # публичный адрес — единственный способ попасть в интернет (за репозиториями
    # пакетов). Входящий трафик на адрес закрыт группой безопасности: открыты
    # только 10051 для агентов и 80 для узлов балансировщика.
    nat                = true
    security_group_ids = [yandex_vpc_security_group.zabbix.id]
  }
}

#ВМ с Elasticsearch: сюда Filebeat с веб-серверов отправляет access.log и error.log
#nginx, отсюда их читает Kibana. Внешнего адреса нет: доступ по внутреннему FQDN
#(elasticsearch.ru-central1.internal), SSH — через bastion. Памяти 4 ГБ и диск 20 ГБ
#(см. var.elasticsearch): на минимальных 2 ГБ Elasticsearch не работает.
resource "yandex_compute_instance" "elasticsearch" {
  name                      = "elasticsearch" #Имя ВМ в облачной консоли
  hostname                  = "elasticsearch" #формирует FDQN имя хоста
  platform_id               = "standard-v3"
  allow_stopping_for_update = true
  zone                      = "ru-central1-a"

  resources {
    cores         = var.elasticsearch.cores
    memory        = var.elasticsearch.memory
    core_fraction = var.elasticsearch.core_fraction
  }

  boot_disk {
    initialize_params {
      image_id = data.yandex_compute_image.ubuntu_2204_lts.image_id
      type     = "network-hdd"
      size     = var.elasticsearch.disk
    }
  }

  metadata = {
    user-data          = file("./cloud-init.yml")
    serial-port-enable = 1
  }

  scheduling_policy { preemptible = var.preemptible }

  network_interface {
    subnet_id          = yandex_vpc_subnet.private_a.id
    nat                = false #внешнего адреса нет: доступ по внутреннему FQDN и через bastion
    security_group_ids = [yandex_vpc_security_group.elk.id]
  }
}

#ВМ с Kibana: веб-интерфейс для поиска по журналам nginx. Размещена в публичной
#подсети public-a; публичный адрес динамический и нужен только для установки
#пакетов. Интерфейс публикуется через балансировщик (listener 5601), SSH — через bastion.
resource "yandex_compute_instance" "kibana" {
  name                      = "kibana" #Имя ВМ в облачной консоли
  hostname                  = "kibana" #формирует FDQN имя хоста
  platform_id               = "standard-v3"
  allow_stopping_for_update = true
  zone                      = "ru-central1-a"

  resources {
    cores         = var.kibana.cores
    memory        = var.kibana.memory
    core_fraction = var.kibana.core_fraction
  }

  boot_disk {
    initialize_params {
      image_id = data.yandex_compute_image.ubuntu_2204_lts.image_id
      type     = "network-hdd"
      size     = var.kibana.disk
    }
  }

  metadata = {
    user-data          = file("./cloud-init.yml")
    serial-port-enable = 1
  }

  scheduling_policy { preemptible = var.preemptible }

  network_interface {
    subnet_id = yandex_vpc_subnet.public_a.id
    # публичная подсеть: публичный адрес нужен только для установки пакетов
    # (маршрута по умолчанию в подсети нет). Входящий трафик закрыт группой
    # безопасности: интерфейс открыт через слушатель 5601 балансировщика,
    # SSH — через bastion.
    nat                = true
    security_group_ids = [yandex_vpc_security_group.elk.id]
  }
}

#Инвентарь для Ansible. Внутренние ВМ адресуются по FQDN в зоне ru-central1.internal,
#а не по IP — адреса ВМ меняются при пересоздании, имена остаются.
#Bastion указан публичным IP: он точка входа извне VPC, по внутреннему имени
#с машины-контроллера (192.168.1.88) он не резолвится.
#Группа internal — ВМ внутреннего контура: подключение через ProxyCommand на bastion
#(ansible_ssh_common_args). Так как через bastion идут все подключения, здесь же
#задан пользователь (ansible_user) — cloud-init создаёт на ВМ пользователя user,
#и плейбуки запускаются без дополнительных ключей командной строки.
resource "local_file" "inventory" {
  content  = <<-XYZ
  [bastion]
  ${yandex_compute_instance.bastion.network_interface.0.nat_ip_address}

  [bastion:vars]
  ansible_user=user

  [webservers]
  ${yandex_compute_instance.web_a.hostname}.ru-central1.internal
  ${yandex_compute_instance.web_b.hostname}.ru-central1.internal

  [zabbix]
  ${yandex_compute_instance.zabbix.hostname}.ru-central1.internal

  [elk]
  ${yandex_compute_instance.elasticsearch.hostname}.ru-central1.internal
  ${yandex_compute_instance.kibana.hostname}.ru-central1.internal

  [elasticsearch]
  ${yandex_compute_instance.elasticsearch.hostname}.ru-central1.internal

  [kibana]
  ${yandex_compute_instance.kibana.hostname}.ru-central1.internal

  [internal:children]
  webservers
  zabbix
  elk

  [internal:vars]
  ansible_user=user
  ansible_ssh_common_args='-o ProxyCommand="ssh -p 22 -W %h:%p -q user@${yandex_compute_instance.bastion.network_interface.0.nat_ip_address}"'
  XYZ
  filename = "./hosts.ini"
}
