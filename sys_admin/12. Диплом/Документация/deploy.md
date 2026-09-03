# Инструкция по разворачиванию копии инфраструктуры

> Пошаговое руководство по полному воспроизведению дипломной инфраструктуры в Yandex Cloud:
> веб-кластер за сетевым балансировщиком (ALB), мониторинг Zabbix (USE),
> сбор логов ELK (Elasticsearch + Kibana + Filebeat), резервное копирование (snapshot schedule).

---

## 0. Что в результате получится

```
                     Internet
                        │
         ┌──────────────┼───────────────┐
         │              │               │
    ALB (<pub>:80)   Zabbix UI     Kibana UI
         │          (<pub>/zabbix)  (<pub>:5601)
    ┌────┴────┐        │               │
   web-a    web-b   Zabbix Server   Kibana → Elasticsearch
  10.0.1.21 10.0.2.10 10.0.1.30      10.0.1.32    10.0.1.31
         │              │               │            │
         └──── Zabbix Agent 2 ──────────┘            │
                 (на всех ВМ)                        │
              bastion (jump-host)                    │
         Filebeat (docker) на web-a/web-b ───────────┘
```

| Компонент | Источник | Назначение |
|-----------|----------|------------|
| Сеть, SG, ВМ, ALB, snapshot | Terraform (`project/task-1/`) | IaC-основа |
| Zabbix Server + агенты | `mon-files/` (вне Terraform) | Мониторинг USE |
| ELK (ES + Kibana) | Terraform cloud-init (Docker) | Логи |
| Filebeat на web-нодах | Ручная установка через SSH | Логи nginx → ES |

**Стоимость:** ВМ `zabbix` (2 vCPU / 4 ГБ / 100% core_fraction) — недешёвая; остальные `preemptible`
(в ~5–7× дешевле). Полная копия ≈ цена одной непрерываемой ВМ + несколько прерываемых.

---

## 1. Предварительные требования

### 1.1. Аккаунт Yandex Cloud
- Платёжный аккаунт с картой или грантом.
- **Каталог** (folder) и значения `cloud_id`, `folder_id`
  (консоль → вкладка каталога, либо `yc resource-manager folder list`).

### 1.2. ПО на рабочей машине (Windows)
- **Docker Desktop** (WSL2) — Terraform запускается в Linux-контейнере (провайдеры `linux_amd64`).
- **YC CLI** (`yc`) — сервисный аккаунт и ручные операции.
- **SSH-клиент** (`ssh`, `scp`) — настройка ВМ.

### 1.3. SSH-ключ
```powershell
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\unikor -N '""'
Get-Content $env:USERPROFILE\.ssh\unikor.pub
```
> ВАЖНО: во всех `cloud-init*.yml` стоит **чужой** ключ `ssh-ed25519 AAAAC3... mixa@DESKTOP-M6JPQEJ`.
> Замените его на **свой** публичный ключ в файлах: `cloud-init.yml`, `cloud-init-es.yml`,
> `cloud-init-kibana.yml`, `mon-files/cloud-init-web.yml`, `mon-files/cloud-init-bastion.yml`,
> `mon-files/cloud-init-zabbix.yml`. Иначе вы не зайдёте на ВМ по SSH.

---

## 2. Сервисный аккаунт и авторизованный ключ

Terraform авторизуется через ключ (`providers.tf`): `service_account_key_file = file("~/.authorized_key.json")`.

```powershell
yc config set cloud-id  <Ваш_CLOUD_ID>
yc config set folder-id <Ваш_FOLDER_ID>

# сервисный аккаунт
$SA = yc iam service-account create --name terraform-sa --format json | ConvertFrom-Json
$SA_ID = $SA.id

# роли для диплома
yc resource-manager folder add-access-binding <Ваш_FOLDER_ID> --subject service-account:$SA_ID --role editor
yc resource-manager folder add-access-binding <Ваш_FOLDER_ID> --subject service-account:$SA_ID --role vpc.publicAdmin
yc resource-manager folder add-access-binding <Ваш_FOLDER_ID> --subject service-account:$SA_ID --role load-balancer.admin
yc resource-manager folder add-access-binding <Ваш_FOLDER_ID> --subject service-account:$SA_ID --role compute.admin

# авторизованный ключ в домашний каталог
yc iam key create --service-account-id $SA_ID --output "$env:USERPROFILE\.authorized_key.json"
```

---

## 3. Рабочая директория (junction без кириллицы)

Путь диплома содержит кириллицу — Terraform/провайдеры в Windows ломаются. Создаём junction:
```powershell
New-Item -ItemType Junction -Path "C:\tf-diploma" `
  -Target "d:\Документы\Manual\Нитология\sys_admin\12. Диплом\project\task-1"
```
Проверьте, что `C:\tf-diploma` содержит `providers.tf`, `variables.tf`, `network.tf`, `vms.tf`,
`elk.tf`, `sg-elk.tf`, `alb.tf`, `backup.tf`, `cloud-init*.yml`, `filebeat.yml`.
Папка `mon-files\` (Zabbix) лежит рядом: `d:\...\12. Диплом\mon-files\`.

---

## 4. Переменные Terraform

В `C:\tf-diploma\variables.tf` подставьте **свои** значения:
```hcl
variable "flow"     { default = "24-01" }            # суффикс имён ресурсов
variable "cloud_id" { default = "<Ваш_CLOUD_ID>" }
variable "folder_id"{ default = "<Ваш_FOLDER_ID>" }
```
И проверьте свой SSH-ключ во всех `cloud-init*.yml` (п. 1.3).

---
## 5. Развертывание основной инфраструктуры (Terraform)

### 5.1. Запуск через Docker (Windows)
Terraform запускается в контейнере, чтобы использовать `linux_amd64`-провайдеры. Монтируем junction и домашний каталог (для `~/.authorized_key.json`):

```powershell
cd C:\tf-diploma

# init — скачивает провайдеры yandex (0.129.0) и local (2.9.0)
docker run --rm -it `
  -v "${PWD}:/work" `
  -v "${env:USERPROFILE}:/root" `
  -w /work `
  hashicorp/terraform:1.14.0 init

# план (проверка: сеть, 3 ВМ, ES, Kibana, ALB, snapshot schedule, SG)
docker run --rm -it `
  -v "${PWD}:/work" -v "${env:USERPROFILE}:/root" -w /work `
  hashicorp/terraform:1.14.0 plan

# apply — разворачивает инфраструктуру (~5–8 минут)
docker run --rm -it `
  -v "${PWD}:/work" -v "${env:USERPROFILE}:/root" -w /work `
  hashicorp/terraform:1.14.0 apply -auto-approve
```
> Монтирование `${env:USERPROFILE}:/root` делает `~/.authorized_key.json` доступным как
> `/root/.authorized_key.json` внутри контейнера.

### 5.2. Что создастся автоматически (cloud-init)
| ВМ | Что ставит cloud-init |
|----|----------------------|
| `bastion` | пользователь `user` + sudo, SSH-ключ |
| `web-a`, `web-b` | nginx + страница сайта |
| `elasticsearch` (10.0.1.31) | Docker + `elasticsearch:7.17.28` (single-node, security off) |
| `kibana` (10.0.1.32) | Docker + `kibana:7.17.28`, `ELASTICSEARCH_HOSTS=http://10.0.1.31:9200` |
| ALB | target group (web-a, web-b:80), backend, router, listener:80, статический public IP |
| snapshot schedule | ежедневно 02:00 UTC, retention 7 дней (диски bastion, web-a, web-b) |

### 5.3. Получить выходные IP
```powershell
cd C:\tf-diploma
docker run --rm -it -v "${PWD}:/work" -v "${env:USERPROFILE}:/root" -w /work hashicorp/terraform:1.14.0 output
```
Сохраните: `balancer_public_ip`, `bastion_public_ip`, `kibana_public_ip`, `elasticsearch_internal_ip`.

### 5.4. Проверка сайта
```powershell
curl http://<balancer_public_ip>/
```
Должна отдаться страница «🚀 Nginx за Application Load Balancer» (HTTP 200). Несколько обновлений
страницы покажут переключение между web-a и web-b (балансировка).

---
## 6. Развёртывание мониторинга (Zabbix) — вне Terraform

Zabbix-сервер не описан в Terraform (создан отдельно). Воспроизводим через YC CLI + cloud-init из `mon-files/`.

### 6.1. Группа безопасности `zabbix_sg`
В `network.tf` текущей версии её нет — создаём вручную:
```powershell
$NET = yc vpc network list --format json | ConvertFrom-Json | ? { $_.name -like "develop-fops-*" } | select -first 1
$NET_ID = $NET.id

$SG = yc vpc security-group create `
  --name "zabbix-sg-24-01" `
  --network-id $NET_ID `
  --rule direction=ingress,port=80,protocol=tcp,v4-cidrs=0.0.0.0/0 `
  --rule direction=ingress,port=443,protocol=tcp,v4-cidrs=0.0.0.0/0 `
  --rule direction=ingress,port=22,protocol=tcp,v4-cidrs=0.0.0.0/0 `
  --rule direction=ingress,port=10051,protocol=tcp,v4-cidrs=10.0.0.0/8 `
  --rule direction=egress,protocol=any,v4-cidrs=0.0.0.0/0 `
  --format json
$SG_ID = ($SG | ConvertFrom-Json).id
```
> Порт 10051 открыт только из `10.0.0.0/8` — агенты слать метрики могут, наружу сервер не торчит.

### 6.2. ВМ Zabbix Server
Подставьте `SUBNET_ID` подсети `develop_a` и `LAN_SG_ID` (группа `LAN-sg-*`):
```powershell
$SUB = yc vpc subnet list --format json | ConvertFrom-Json | ? { $_.name -like "develop-fops-*-ru-central1-a" } | select -first 1
$LAN = yc vpc security-group list --format json | ConvertFrom-Json | ? { $_.name -like "LAN-sg-*" } | select -first 1

# путь без кириллицы (иначе YC ломается); впишите свой SSH-ключ в mon-files\cloud-init-zabbix.yml (п.1.3)
Copy-Item "d:\Документы\Manual\Нитология\sys_admin\12. Диплом\mon-files\cloud-init-zabbix.yml" "$env:TEMP\ci-zabbix.yml"

yc compute instance create `
  --name zabbix --hostname zabbix `
  --zone ru-central1-a `
  --network-interface subnet-id=$($SUB.id),ipv4-address=10.0.1.30,nat=true,security-group-ids=$($LAN.id),$SG_ID `
  --create-boot-disk image-folder-id=standard-images,image-family=ubuntu-2204-lts,type=network-hdd,size=15 `
  --memory 4 --cores 2 --core-fraction 100 `
  --preemptible `
  --metadata-from-file user-data=$env:TEMP\ci-zabbix.yml
```
cloud-init установит Zabbix Server 7.0 (PostgreSQL 16 + Apache + Agent 2), импортирует схему БД,
поставит пароль `zabbix`, таймзону Europe/Moscow и запустит сервисы. Это занимает ~5–7 минут.

Дождитесь готовности UI:
```powershell
$ZBX_PUB = (yc compute instance get zabbix --format json | ConvertFrom-Json).network_interfaces[0].primary_v4_address.one_to_one_nat.address
curl "http://$ZBX_PUB/zabbix/"   # должна быть страница входа Zabbix
```
Учётные данные по умолчанию: **Admin / zabbix**.

### 6.3. Zabbix Agent 2 на web-a / web-b / bastion
Текущий `cloud-init.yml` ставит только nginx, без агента. Два пути:

**Вариант A (до apply):** заменить `cloud-init.yml` в `vms.tf` на отдельные файлы из `mon-files/` —
`cloud-init-web.yml` (web) и `cloud-init-bastion.yml` (bastion). В них уже встроены Zabbix Agent 2,
`stub_status` для nginx и авто-регистрация (`HostMetadata=diploma web`). После замены пересоздайте
ВМ: `terraform destroy -target yandex_compute_instance.web_a && terraform apply`
(**cloud-init не перезапускается при обновлении metadata**).

**Вариант B (ручной, после apply):** зайти на каждую ВМ по SSH и установить агент:
```bash
# на web-a через zabbix как jump-host (bastion:22 может таймаутить):
ssh -i ~/.ssh/unikor -J user@<ZBX_PUB> user@10.0.1.21
sudo bash -c '
wget -q https://repo.zabbix.com/zabbix/7.0/ubuntu/pool/main/z/zabbix-release/zabbix-release_7.0-2+ubuntu22.04_all.deb -O /tmp/zabbix-release.deb
dpkg -i /tmp/zabbix-release.deb && apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y zabbix-agent2
cat > /etc/zabbix/zabbix_agent2.d/diploma.conf <<EOF
Server=10.0.1.30
ServerActive=10.0.1.30
HostnameItem=system.hostname
HostMetadata=diploma web
RefreshActiveChecks=60
EOF
systemctl enable --now zabbix-agent2
'
```
Повторить для web-b (10.0.2.10) и bastion (10.0.1.24, `HostMetadata=diploma bastion`).
Для web-нод также добавьте блок `/nginx_status` (stub_status) в nginx — см. `mon-files/cloud-init-web.yml`.

### 6.4. Автонастройка Zabbix (хосты, шаблоны, USE-дашборд)
Скопируйте `zbx-configure.sh` на Zabbix-сервер и запустите (идемпотентный, через API):
```powershell
scp -i ~/.ssh/unikor "d:\Документы\Manual\Нитология\sys_admin\12. Диплом\mon-files\zbx-configure.sh" user@$ZBX_PUB:/tmp/
ssh -i ~/.ssh/unikor user@$ZBX_PUB 'chmod +x /tmp/zbx-configure.sh && sudo /tmp/zbx-configure.sh'
```
Скрипт создаст: группу `Diploma`, хосты `web-a`/`web-b`/`bastion`/`zabbix`, линковку шаблонов
`Linux by Zabbix agent` + `Nginx by Zabbix agent`, HTTP-метрики и USE-триггеры на web-узлах,
дашборд **«USE Monitoring — Diploma»** (14 виджетов). Лог: `/var/log/zabbix-setup.log`.

---
## 7. Логи: Filebeat на web-нодах + index pattern в Kibana

### 7.1. Filebeat (docker) на web-a и web-b
ES и Kibana уже подняты cloud-init. Filebeat ставится вручную. На каждой web-ноде:
```bash
ssh -i ~/.ssh/unikor -J user@<ZBX_PUB> user@10.0.1.21   # для web-b — user@10.0.2.10
sudo bash -c '
apt-get update && apt-get install -y docker.io
systemctl enable --now docker
docker run -d --name filebeat --restart unless-stopped \
  -v /var/log/nginx:/var/log/nginx:ro \
  -v /etc/filebeat/filebeat.yml:/usr/share/filebeat/filebeat.yml:ro \
  -e SERVER_NAME=web-a \
  elastic/filebeat:7.17.28
'
```
> Для web-b используйте `-e SERVER_NAME=web-b`. Конфиг `filebeat.yml` (он же в `C:\tf-diploma\filebeat.yml`):
> два input (`access.log` → `log_type: nginx_access`, `error.log` → `log_type: nginx_error`),
> `output.elasticsearch.hosts: ["10.0.1.31:9200"]`, ILM/template отключены, поле `server` из env.

Скопировать конфиг на ВМ:
```powershell
scp -i ~/.ssh/unikor -J user@<ZBX_PUB> "C:\tf-diploma\filebeat.yml" user@10.0.1.21:/tmp/filebeat.yml
ssh -i ~/.ssh/unikor -J user@<ZBX_PUB> user@10.0.1.21 "sudo mv /tmp/filebeat.yml /etc/filebeat/filebeat.yml"
```
Проверка отправки логов:
```bash
docker logs filebeat | grep -i established
# Connection to backoff(elasticsearch(http://10.0.1.31:9200)) established
```
Сгенерируйте трафик: `curl http://<balancer_public_ip>/` несколько раз — документы в ES начнут расти.

### 7.2. Index pattern `filebeat-*` в Kibana
Kibana доступна по `http://<kibana_public_ip>:5601`. Создаём index pattern через API
(файлы `kibana-idx.json`, `kibana-cfg.json`, `kibana-setup.sh`):
```bash
ssh -i ~/.ssh/unikor user@<KIBANA_PUB>   # kibana:22 открыт в SG kibana_sg
# скопировать json и скрипт на ВМ, затем:
sudo bash /tmp/kibana-setup.sh
```
> `kibana-setup.sh` делает POST `/api/saved_objects/index-pattern` (title `filebeat-*`, timeField
> `@timestamp`) и PUT `/api/saved_objects/config` (defaultIndex `filebeat-*`). После этого в Kibana
> **Discover** появятся логи nginx.

Проверка: в браузере `http://<kibana_public_ip>:5601/app/discover` → выбрать `filebeat-*` → видны
документы с `server: web-a` / `server: web-b`.

---

## 8. Резервное копирование диска Zabbix

`backup.tf` включает в snapshot schedule только TF-managed ВМ (bastion, web-a, web-b). Диск Zabbix
добавляется вручную:
```powershell
$ZBX_DISK = (yc compute instance get zabbix --format json | ConvertFrom-Json).boot_disk.disk_id
yc compute snapshot-schedule add-disks --name daily-snapshot-24-01 --disk-id $ZBX_DISK
```
Проверка:
```powershell
yc compute snapshot-schedule get daily-snapshot-24-01
# status = ACTIVE, retention_period = 168h, expression = "0 2 * * *"
```

---

## 9. Доступ к внутренним ВМ (jump-host)

Прямой SSH на bastion (порт 22) в этой конфигурации YC может **таймаутить** (особенность NAT YC).
Рабочий путь — через Zabbix как ProxyJump:
```powershell
ssh -i ~/.ssh/unikor -J user@<ZBX_PUB> user@10.0.1.31   # elasticsearch
ssh -i ~/.ssh/unikor -J user@<ZBX_PUB> user@10.0.1.21   # web-a
ssh -i ~/.ssh/unikor -J user@<ZBX_PUB> user@10.0.2.10   # web-b
ssh -i ~/.ssh/unikor -J user@<ZBX_PUB> user@10.0.1.32   # kibana (внутр.)
```
> IP Zabbix и Kibana **эфемерны** (nat=true без статического) — после stop/start ВМ они меняются.
> Перевыпишите их из `terraform output` / `yc compute instance get`.

---
## 10. Финальный чек-лист (проверка копии)

| # | Проверка | Команда / действие | Ожидаемый результат |
|---|----------|--------------------|---------------------|
| 1 | Сайт | `curl http://<balancer_public_ip>/` | HTTP 200, страница «Nginx за ALB» |
| 2 | Балансировка | несколько `curl` | в логах web-a и web-b есть запросы |
| 3 | ES поднят | `curl http://10.0.1.31:9200` (с web-ноды) | JSON `cluster_name: diploma-cluster` |
| 4 | ES документы | `curl http://10.0.1.31:9200/_count` | count растёт после запросов к сайту |
| 5 | Kibana UI | `http://<kibana_public_ip>:5601` | HTTP 200, страница Kibana |
| 6 | index pattern | Kibana → Discover → `filebeat-*` | есть документы `server: web-a/web-b` |
| 7 | Zabbix UI | `http://<zabbix_pub>/zabbix/` | страница входа; Admin/zabbix |
| 8 | Хосты в Zabbix | Monitoring → Hosts | web-a, web-b, bastion, zabbix — зелёные (ZBX) |
| 9 | USE-дашборд | Dashboards → «USE Monitoring — Diploma» | 14 виджетов с графиками |
| 10 | Агенты | Zabbix → Latest data | метрики CPU/память/диск/Nginx поступают |
| 11 | Snapshots | `yc compute snapshot-schedule get daily-snapshot-24-01` | status ACTIVE, retention 168h |
| 12 | Диск Zabbix в schedule | `yc compute snapshot-schedule list-disks ...` | диск zabbix в списке |

---

## 11. Устранение типичных проблем

**`artifacts.elastic.co` отдаёт 403.** В РФ репозиторий Elastic заблокирован. ES/Kibana/Filebeat
ставятся из Docker Hub (`library/elasticsearch:7.17.28`, `library/kibana:7.17.28`,
`elastic/filebeat:7.17.28`) — `registry-1.docker.io` доступен. cloud-init-файлы менять не нужно.

**Terraform не запускается в Windows (провайдеры `linux_amd64`).** Решение — запуск в Docker-контейнере
`hashicorp/terraform:1.14.0` (раздел 5).

**Кириллица в пути ломает Terraform/`yc`.** Junction `C:\tf-diploma` (раздел 3). Для `yc compute instance
create --metadata-from-file` файл cloud-init тоже должен быть на пути без кириллицы (`$env:TEMP`).

**SSH на bastion (22) таймаутит.** Особенность YC NAT. Заходите через Zabbix как ProxyJump
(`-J user@<ZBX_PUB>`, раздел 9). Можно также через серийную консоль:
`yc compute connect-to-serial-port --instance-name bastion`.

**Kibana / Zabbix публичный IP поменялся.** IP эфемерен (nat=true без `yandex_vpc_address`). После
stop/start ВМ берите новый: `terraform output kibana_public_ip` или `yc compute instance get kibana`.
Для постоянного IP — зарезервируйте `yandex_vpc_address` и привяжите.

**cloud-init не перезапускается при `terraform apply` (изменение metadata).** Cloud-init выполняется
один раз при создании ВМ. Чтобы изменить начальную конфигурацию — пересоздайте ВМ:
`terraform taint yandex_compute_instance.web_a && terraform apply`, либо выполните шаги вручную по SSH
(раздел 6.3, вариант B).

**Preemptible ВМ выключились.** ВМ `preemptible=true`, YC может остановить их раз в 24ч. Достаточно
запустить снова (`yc compute instance start`); ES/Kibana/Docker поднимутся автоматически
(`--restart unless-stopped`).

**Zabbix-агенты не регистрируются.** Проверьте `HostMetadata` (`diploma web` / `diploma bastion`) и
`Server=10.0.1.30`. На web-нодах убедитесь, что `stub_status` доступен:
`curl http://127.0.0.1/nginx_status`. Перепроверьте, что SG `LAN` разрешает 10050/10051 из 10.0.0.0/8.

**`jq missing` в zbx-configure.sh.** cloud-init-zabbix.yml уже ставит `jq`. Если вручную —
`sudo apt-get install -y jq`.

---

## 12. Уничтожение копии (по окончании)

```powershell
cd C:\tf-diploma
docker run --rm -it -v "${PWD}:/work" -v "${env:USERPROFILE}:/root" -w /work `
  hashicorp/terraform:1.14.0 destroy -auto-approve
# Zabbix-сервер — отдельно (вне Terraform):
yc compute instance delete zabbix
yc vpc security-group delete zabbix-sg-24-01
```
> Снимки по retention удалятся автоматически через 7 дней (или вручную:
> `yc compute snapshot-schedule delete daily-snapshot-24-01`).

---

## Приложение. Сводный список IP-адресов (шаблон)

| Роль | Внутренний | Публичный | Примечание |
|------|-----------|-----------|------------|
| bastion | 10.0.1.x (DHCP) | ephemeral | jump-host (22 таймаутит → через zabbix) |
| web-a | 10.0.1.21 | — | nginx + Filebeat + Zabbix agent |
| web-b | 10.0.2.10 | — | nginx + Filebeat + Zabbix agent |
| elasticsearch | 10.0.1.31 | — | Docker, 9200 из 10.0.0.0/8 |
| kibana | 10.0.1.32 | ephemeral | Docker, 5601 из 0.0.0.0/0 |
| zabbix | 10.0.1.30 | ephemeral | Server 7.0 + Agent 2, UI /zabbix |
| ALB | — | статический (yandex_vpc_address) | 80 → web-a/web-b |

Все конкретные адреса подставляйте из `terraform output` и `yc compute instance get` после разворачивания.

---

*Инструкция основана на фактически развёрнутой инфраструктуре диплома (см. `info.md`).*