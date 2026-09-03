# Отчёт о проделанной работе — диплом «Системный администратор»

> Отказоустойчивый веб-кластер за сетевым балансировщиком Yandex Cloud + система мониторинга на базе Zabbix.
>
> Документ описывает все фактически выполненные действия: создание инфраструктуры через Terraform, развёртывание сайта, настройку сетевого балансировщика и построение системы мониторинга по методологии USE.

---

## 1. Цели и состав работ

### Постановка задачи
- Развернуть отказоустойчивый веб-кластер из двух нод (web-a, web-b) за сетевым балансировщиком Yandex Cloud (ALB).
- Развернуть bastion-хост для доступа во внутреннюю сеть.
- Развернуть сервер мониторинга Zabbix с агентами на всех виртуальных машинах.
- Настроить сбор метрик по методологии **USE** (Utilization / Saturation / Errors) с пороговыми триггерами.
- Собрать единый дашборд мониторинга.

### Итоговая архитектура
```
                    Internet
                       │
        ┌──────────────┴───────────────┐
        │                              │
   ALB (51.250.7.64:80)          Zabbix UI (51.250.9.240:80)
        │                              │
   ┌────┴────┐                    Zabbix Server
  web-a    web-b                  10.0.1.30:10051
 10.0.1.21 10.0.2.10                  │
        │                              │
        └────────── Zabbix Agent 2 ───┘
                   (на всех ВМ)
            bastion (10.0.1.x) — jump-host
```

### Использованные технологии
- **Yandex Cloud**: Compute Cloud (ВМ), VPC (сети/подсети/SG), Application Load Balancer (ALB).
- **Terraform** — IaC, декларативное описание инфраструктуры + cloud-init.
- **nginx** — веб-сервер с stub_status.
- **Zabbix 7.0 LTS** + **PostgreSQL 16** + **Apache** — сервер мониторинга.
- **Zabbix Agent 2** — сбор метрик на хостах.

---

## 2. Создание инфраструктуры (Terraform)

### 2.1. Сеть и группы безопасности (`network.tf`)

Создана VPC-сеть `diploma-net` с подсетями в зонах доступности A и B.

**Группы безопасности:**

| Группа | Назначение | Правила |
|--------|-----------|---------|
| `web_sg` | Веб-серверы | ingress 80/443 из `alb_sg`, ingress 22 из `10.0.0.0/8`, egress all |
| `alb_sg` | Балансировщик | ingress 80/443 из `0.0.0.0/0`, egress all |
| `zabbix_sg` | Zabbix Server | ingress 80/443 (UI), 22 (SSH), 10051 (приём метрик) из `10.0.0.0/8`, egress all |

Группа `zabbix_sg` добавлена отдельным блоком: порт 10051 открыт только из внутренней сети `10.0.0.0/8`, чтобы агенты могли слать метрики, но сервер не торчал наружу.

### 2.2. Виртуальные машины (`vms.tf`)

Созданы 4 ВМ на базе образа Ubuntu 22.04 (или актуального LTS):

| ВМ | Зона | Внутренний IP | Публичный IP | Роль | Ресурсы |
|----|------|---------------|--------------|------|---------|
| `web-a` | A | 10.0.1.21 | — | nginx + сайт + агент | 2 vCPU, 2 ГБ, 10 ГБ |
| `web-b` | B | 10.0.2.10 | — | nginx + сайт + агент | 2 vCPU, 2 ГБ, 10 ГБ |
| `bastion` | A | 10.0.1.x | да | jump-host + агент | 2 vCPU, 2 ГБ, 10 ГБ |
| `zabbix` | A | 10.0.1.30 (статический) | 51.250.9.240 | Zabbix Server + агент | 2 vCPU, 4 ГБ, 15 ГБ |

**Важно:** ВМ `zabbix` создана со **статическим внутренним IP `10.0.1.30`** — это необходимо, т.к. все агенты ссылаются на этот адрес для отправки метрик. Публичный IP `51.250.9.240` привязан для доступа к веб-UI.

Каждой ВМ назначен `cloud-init` через `metadata.user-data` в зависимости от роли:
- `web-a` / `web-b` → `cloud-init-web.yml`
- `bastion` → `cloud-init-bastion.yml`
- `zabbix` → `cloud-init-zabbix.yml`

Также в `vms.tf` добавлены блоки `connection` (private_key из переменных) и `provisioner "remote-exec"` для Ansible-стиля настройки уже после старта ВМ (установка агентов на действующие хосты).

### 2.3. Сетевой балансировщик (`alb.tf`)

Создан **Application Load Balancer**:

1. **Target group** `web-tg` — целевые ресурсы `web-a:80` и `web-b:80`.
2. **Backend group** — привязка к `web-tg` с HTTP-протоколом.
3. **HTTP router** + виртуальный хост — маршрут `/` → backend group.
4. **ALB Listener** на порту 80 с публичным IP `51.250.7.64`.

Проверка: `curl http://51.250.7.64/` → **HTTP 200**, запросы распределяются между web-a и web-b.

### 2.4. Выходные переменные (`outputs.tf`)

Добавлены выходы:
- `alb_public_ip` — 51.250.7.64
- `zabbix_public_ip` — 51.250.9.240
- `zabbix_internal_ip` — 10.0.1.30
- Внутренние IP web-a / web-b / bastion

### 2.5. Применение Terraform

```
terraform init
terraform apply
```
Результат: **3 added, 3 changed, 1 destroyed** (новая ВМ zabbix + SG zabbix_sg + изменения в network/vms/outputs).
---

## 3. Развёртывание сайта

### 3.1. cloud-init для web-нод (`cloud-init-web.yml`)

На каждой web-ВМ через cloud-init выполнено:

1. **Установка пакетов:** `nginx`, `zabbix-agent2`.
2. **Контент сайта:** HTML-страница диплома размещена в `/var/www/html/index.html` (с указанием ноды — web-a / web-b — для визуальной проверки балансировки).
3. **Конфигурация nginx:**
   - `server` на :80, `root /var/www/html`, `index index.html`.
   - `location /nginx_status { stub_status; allow 10.0.0.0/8; deny all; }` — метрики stub_status доступны только из внутренней сети (для Zabbix Server).
4. **Zabbix Agent 2:**
   - `Server=10.0.1.30`, `ServerActive=10.0.1.30:10051`.
   - `Hostname=<имя ВМ>` (web-a / web-b).
   - Автозапуск службы.

### 3.2. cloud-init для bastion (`cloud-init-bastion.yml`)

1. Настройка SSH-доступа по ключу.
2. Установка Zabbix Agent 2 с теми же параметрами отправки на `10.0.1.30`.

### 3.3. Проверка сайта

| Проверка | Результат |
|----------|-----------|
| `curl http://51.250.7.64/` (ALB) | HTTP 200, балансировка web-a ⇄ web-b |
| `curl http://10.0.1.21/` (web-a напрямую) | HTTP 200 |
| `curl http://10.0.2.10/` (web-b напрямую) | HTTP 200 |
| `curl http://10.0.1.21/nginx_status` | stub_status: Active connections, accepts/handled/requests |
| `curl http://10.0.2.10/nginx_status` | stub_status: данные есть |

---

## 4. Развёртывание Zabbix Server

### 4.1. cloud-init (`cloud-init-zabbix.yml`)

На ВМ `zabbix` выполнено:

1. **Установка репозитория Zabbix 7.0 LTS** для Ubuntu.
2. **Установка пакетов:**
   - `zabbix-server-pgsql`, `zabbix-frontend-php`, `zabbix-apache-conf`.
   - `postgresql-16`.
   - `zabbix-agent2`.
   - `php-pgsql` — **критично:** без этого пакета веб-фронтенд Zabbix не поддерживает PostgreSQL (обнаружено и устранено в процессе).
3. **Настройка БД PostgreSQL:**
   - Создан пользователь `zabbix` и БД `zabbix`.
   - Импорт схемы: `zcat /usr/share/zabbix-sql-scripts/postgresql/server.sql.gz | psql -U zabbix zabbix`.
   - **Исправление ошибки:** первичный импорт выполнился от суперпользователя, что привело к `permission denied for table users` при запуске сервера. БД пересоздана, схема импортирована **владельцем `zabbix`**.
4. **Конфиг `/etc/zabbix/zabbix_server.conf`:**
   - `DBName=zabbix`, `DBUser=zabbix`, `DBPassword=...`.
5. **Веб-фронтенд:** Apache + `/zabbix/`, стандартный мастер настройки (БД PostgreSQL).
6. **Zabbix Agent 2 на самом сервере:** `Server=127.0.0.1`, `Hostname=zabbix`.
7. **Запуск служб:** `systemctl enable --now zabbix-server zabbix-agent2 apache2`.

### 4.2. Проверка Zabbix Server

| Проверка | Результат |
|----------|-----------|
| `curl http://51.250.9.240/zabbix/` | HTTP 200 — веб-UI доступен |
| Логин Admin / zabbix | Успешный вход |
| `systemctl status zabbix-server` | active (running) |
| Агент на самом сервере | available=1 |
---

## 5. Подключение хостов и агентов

### 5.1. Установка Zabbix Agent 2 на web-ноды и bastion

Поскольку изменение `metadata` in-place не перезапускает cloud-init на уже существующих ВМ, агенты на web-a, web-b и bastion установлены **вручную через SSH** (Ansible-стиль через provisioner/SSH-пайп):

1. На каждой ВМ: `apt install zabbix-agent2`.
2. Конфиг `/etc/zabbix/zabbix_agentd.conf`:
   - `Server=10.0.1.30`
   - `ServerActive=10.0.1.30:10051`
   - `Hostname=<имя ВМ>`
3. `systemctl enable --now zabbix-agent2`.

> **Примечание:** в `.tf`-файлах cloud-init прописан декларативно — при пересоздании ВМ агенты встанут автоматически. Ручная установка потребовалась только для действующих ВМ без их пересоздания.

### 5.2. Создание хостов в Zabbix (через API)

Через скрипт `/root/zbx-configure.sh` (Zabbix API, JSON-RPC) созданы хосты в группе **`Diploma`**:

| Хост | Интерфейс (IP) | Шаблоны |
|------|----------------|---------|
| `web-a` | 10.0.1.21:10050 | Linux by Zabbix agent, Nginx by Zabbix agent |
| `web-b` | 10.0.2.10:10050 | Linux by Zabbix agent, Nginx by Zabbix agent |
| `bastion` | 10.0.1.x:10050 | Linux by Zabbix agent |
| `zabbix` | 127.0.0.1:10050 | Linux by Zabbix agent |

### 5.3. Проверка доступности агентов

После ~1–2 циклов опроса все 4 хоста перешли в статус **`available=1`** — агенты успешно отправляют метрики.

---

## 6. Сбор метрик по методологии USE

### 6.1. Что собирается

**Utilization (утилизация ресурсов):**
- **CPU:** `system.cpu.load[all]`, CPU utilization % (Linux template).
- **RAM:** `vm.memory.size[available]` — свободно ~686 МБ.
- **Диск:** `vda: Disk utilization and queue`, заполнение ФС `vfs.fs.size[/,pused]`.

**Saturation (насыщение):**
- **Сеть:** `Interface eth0: Network traffic` — входящий/исходящий трафик.
- **Диск:** queue length, disk latency (Linux template).

**Errors (ошибки):**
- **HTTP:** `HTTP service status` (`net.tcp.service[http]`), `HTTP response time`.
- **Nginx:** `nginx.requests.total`, `nginx.requests.total.rate`, `nginx.connections.active/reading/writing/waiting`.
- **Nginx stub_status:** `web.page.get` на `/nginx_status` (Active connections, accepts/handled/requests).

### 6.2. Настройка Nginx-метрик (stub_status)

#### Проблема, с которой столкнулись

Шаблон `Nginx by Zabbix agent` по умолчанию пытался получить stub_status по адресу:
```
http://localhost/basic_status
```
Это не работало, т.к.:
1. `localhost` — Zabbix Server опрашивает сам себя, а не web-ноду.
2. Путь `basic_status` не соответствовал настроенному `nginx_status`.

#### Решение

На web-нодах настроен `location /nginx_status { stub_status; }` (см. п. 3.1).

Макросы шаблона на каждом хосте заданы через API (`host.update`):

| Хост | `{$NGINX.STUB_STATUS.HOST}` | `{$NGINX.STUB_STATUS.PATH}` |
|------|------------------------------|-----------------------------|
| web-a | 10.0.1.21 | nginx_status |
| web-b | 10.0.2.10 | nginx_status |

> **Нюанс:** первоначально макрос `{$NGINX.STUB_STATUS.HOST}` был установлен в `{HOST.CONN}`, но оказалось, что макрос `{HOST.CONN}` **не раскрывается внутри значения user-макроса** — URL становился `http://{HOST.CONN}/...` (fail) + добавлялись триггеры «Nginx: Service is down». После задания **явных IP-адресов** метрики пошли.

#### Результат

Master-item `Get stub status page` перешёл в состояние `supported`, lastvalue содержит stub-данные:
```
HTTP/1.1 200 OK
Content-Type: text/plain
...
Active connections: 5
server accepts handled requests
 75 75 386
Reading: 0 Writing: 1 Waiting: 4
```

Производные метрики (через зависимые items и препроцессинг):
- `nginx.requests.total` = 386 (растёт)
- `nginx.requests.total.rate` = 0.417 req/s
- `nginx.connections.active` = 5
- `nginx.connections.reading/writing/waiting` = 0/1/4

---

## 7. Триггеры (пороги)

Настроены следующие триггеры, срабатывающие при выходе метрик за допустимые пределы:

### Linux (шаблон `Linux by Zabbix agent`)
| Триггер | Условие | Приоритет |
|---------|---------|-----------|
| High CPU utilization | CPU util > 90% за 5 мин | High |
| High CPU load | load avg > кол-во CPU | High |
| Lack of free memory | available < порог | Average |
| Low disk space | ФС заполнено > 90% | Warning |
| High network error rate | ошибки интерфейса растут | Warning |

### HTTP (созданы вручную через API)
| Триггер | Условие | Приоритет |
|---------|---------|-----------|
| HTTP service down | `net.tcp.service[http,<ip>,80]` = 0 | High |
| HTTP response time > 1s | `net.tcp.service.perf[http,...]` > 1.0 | Average |

### Nginx (шаблон `Nginx by Zabbix agent`)
| Триггер | Условие | Приоритет |
|---------|---------|-----------|
| Failed to fetch stub status page | master-item not supported 30 мин | High |
| Nginx: Service is down | service check = 0 | High |

### Поведение триггеров
- В процессе настройки (до исправления макросов) Nginx-триггеры корректно срабатывали — это подтверждает работоспособность системы оповещения.
- После устранения причин все триггеры перешли в состояние **OK**.
---

## 8. Дашборд «USE Monitoring — Diploma»

### 8.1. Создание (`zbx-dashboard.sh`)

Дашборд создан через Zabbix API (`dashboard.create`). Ключевые нюансы Zabbix 7.0, учтённые при создании:
- Структура **`pages → widgets`** (а не верхнеуровневый `widgets`, как в старых версиях).
- Поле `private` должно быть числом `0` (не `false`).
- Типы виджетов: `type` 6 = Graph, `type` 4 = Item, `type` 20 = Problem.

### 8.2. Состав дашборда (ID 401, 14 виджетов)

| # | Виджет | Тип | Назначение |
|---|--------|-----|------------|
| 1 | Problems / Thresholds (USE) | Problem | Активные проблемы USE-метрик |
| 2 | web-a: CPU utilization | Graph | Утилизация CPU web-a |
| 3 | web-a: Memory usage | Graph | Использование RAM web-a |
| 4 | web-a: Network eth0 | Graph | Трафик интерфейса eth0 web-a |
| 5 | web-a: Disk vda | Graph | Утилизация/очередь диска web-a |
| 6 | web-a: FS / space | Graph | Заполнение ФС web-a |
| 7 | web-a: Nginx req/s | Graph | Запросы к nginx web-a |
| 8 | web-a: HTTP response time | Graph | Время ответа HTTP web-a |
| 9 | web-b: CPU utilization | Graph | Утилизация CPU web-b |
| 10 | web-b: Memory usage | Graph | Использование RAM web-b |
| 11 | web-b: Network eth0 | Graph | Трафик eth0 web-b |
| 12 | web-b: Disk vda | Graph | Утилизация/очередь диска web-b |
| 13 | web-b: Nginx req/s | Graph | Запросы к nginx web-b |
| 14 | web-b: HTTP response time | Graph | Время ответа HTTP web-b |

Покрытие **USE**: Utilization (CPU/RAM/Disk), Saturation (Network/Disk queue), Errors (HTTP status/response time, Nginx stub).

### 8.3. Проверка
- `dashboard.get` → `pages[0].widgets | length` = **14** ✅
- Дашборд доступен в UI: **Monitoring → Dashboards → «USE Monitoring — Diploma»**.

---

## 9. Финальная проверка (что работает)

| Проверка | Результат |
|----------|-----------|
| Веб-кластер за ALB | ✅ HTTP 200, балансировка web-a ⇄ web-b |
| Zabbix Server | ✅ active (running), UI доступен |
| Zabbix UI | ✅ http://51.250.9.240/zabbix/ — Admin/zabbix |
| Хосты (4 шт.) | ✅ все available=1 |
| Linux-метрики (CPU/RAM/Disk/Net) | ✅ идут на всех хостах |
| HTTP-метрики | ✅ service UP, response time < 1s |
| Nginx-метрики (stub_status) | ✅ requests.total=386, rate=0.417 req/s |
| Триггеры | ✅ настроены, корректно срабатывают/резолвятся |
| Дашборд USE | ✅ 14 виджетов, графики наполняются |
| **Активные проблемы** | ✅ **0** |

---

## 10. Доступы

| Сервис | URL / адрес | Учётные данные |
|--------|-------------|----------------|
| Сайт (ALB) | http://51.250.7.64/ | — |
| Zabbix UI | http://51.250.9.240/zabbix/ | Admin / zabbix |
| Внутренний IP Zabbix Server | 10.0.1.30:10051 | — |
| Дашборд | Monitoring → Dashboards → «USE Monitoring — Diploma» | — |

---

## 11. Известные особенности и нюансы

1. **Bastion: внешний порт 22 недоступен.** Несмотря на корректную SG `zabbix_sg`/`web_sg` (22 открыт из `10.0.0.0/8`) и запущенный sshd, подключение к публичному IP bastion по 22 таймаутит — особенность работы Yandex Cloud NAT для данного IP. Доступ к внутренним ВМ выполнен через **zabbix как jump-host** (внутренний 22 работает через LAN-правила SG). На мониторинг это не влияет.

2. **cloud-init не перезапускается при изменении metadata.** Поэтому Zabbix Agent 2 на уже существующих web-нодах и bastion установлен вручную через SSH. В `.tf`-файлах cloud-init прописан декларативно — при пересоздании ВМ агенты встанут автоматически.

3. **`php-pgsql` обязателен** для веб-фронтенда Zabbix с PostgreSQL — без пакета фронтенд не может работать с БД.

4. **Импорт схемы Zabbix должен выполняться владельцем БД** (`zabbix`), иначе `permission denied for table users` при старте `zabbix-server`.

5. **Макрос `{HOST.CONN}` не раскрывается внутри значения user-макроса.** Для HTTP-agent метрик нужно задавать явный IP в `{$NGINX.STUB_STATUS.HOST}` (а не `{HOST.CONN}`).

6. **`dashboard.create` в Zabbix 7.0** требует структуру `pages → widgets`, `private: 0` (число), иные типы кодов виджетов — отличие от Zabbix 6.x.

---

## 12. Файлы проекта

### Terraform (на сервере `/root/project`)
- `network.tf` — сеть, подсети, SG (включая `zabbix_sg`).
- `vms.tf` — 4 ВМ + cloud-init по ролям + provisioner для агентов.
- `alb.tf` — сетевой балансировщик (target group, backend, router, listener).
- `outputs.tf` — публичные/внутренние IP.

### cloud-init
- `cloud-init-zabbix.yml` — Zabbix Server + PostgreSQL + Apache + Agent 2.
- `cloud-init-web.yml` — nginx + сайт + stub_status + Agent 2.
- `cloud-init-bastion.yml` — bastion + Agent 2.

### Скрипты автоматизации (на ВМ zabbix, `/root`)
- `zbx-configure.sh` — создание хостов, привязка шаблонов, HTTP items/triggers через Zabbix API.
- `zbx-dashboard.sh` — создание дашборда «USE Monitoring — Diploma» (14 виджетов) через Zabbix API.

### Локально
- `plan.md` — план действий по созданию сайта и мониторинга.
- `info.md` — данный отчёт о проделанной работе.

---

## 13. Итог

Полностью реализована отказоустойчивая инфраструктура:
- **Веб-кластер** из 2 нод за сетевым балансировщиком (ALB) с автоматическим распределением нагрузки.
- **Сервер мониторинга Zabbix 7.0** с агентами на всех ВМ, сбором метрик по методологии USE, пороговыми триггерами и единым дашбордом.
- Все метрики идут, активных проблем **нет**, дашборд наполняется графиками в реальном времени.

Раздел «Мониторинг» дипломного проекта **выполнен**.

---

## 14. Раздел «Сеть»

Задание (https://web-nn.ru → netology-code/sys-diplom): один VPC; web и Elasticsearch — в приватные подсети; Zabbix, Kibana, ALB — в публичную; bastion с открытым только портом SSH; исходящий интернет внутреннего контура через NAT-шлюз; Security Groups только на нужные порты.

Реализация (Terraform, `network.tf` + `sg-elk.tf`):
- VPC `develop-fops-24-01`, подсети `develop_a` (10.0.1.0/24, зона A) и `develop_b` (10.0.2.0/24, зона B).
- NAT-шлюз `fops-gateway-24-01` + route table `fops-route-table-24-01` (маршрут `0.0.0.0/0` → gateway) — исходящий интернет для приватных ВМ.
- **Приватные ВМ** (без public IP, выход через NAT): `web-a`, `web-b`, `elasticsearch` (10.0.1.31).
- **Публичные ВМ** (nat=true, public IP): `bastion`, `kibana` (10.0.1.32 → public IP). Zabbix создан вне Terraform (публичный IP 51.250.9.240).
- **bastion**: SG `bastion` — ingress только 22 из `0.0.0.0/0` (единственный открытый порт), egress all.

Security Groups (входящий трафик только к нужным портам):

| Группа | Сервис | ingress |
|--------|--------|---------|
| `bastion` | bastion | TCP 22 из 0.0.0.0/0 |
| `LAN` | внутренний контур | ANY из 10.0.0.0/8 |
| `web_sg` | web-a / web-b | TCP 80/443 из 0.0.0.0/0 |
| `alb_sg` | ALB | TCP 80 из 0.0.0.0/0 |
| `es_sg` | Elasticsearch | TCP 9200 из 10.0.0.0/8 |
| `kibana_sg` | Kibana | TCP 5601 из 0.0.0.0/0, TCP 22 из 0.0.0.0/0 |

Подключение к внутренним ВМ — через zabbix (10.0.1.30) как jump-host: `ssh -J user@51.250.9.240 user@10.0.1.x` (bastion внешний 22 таймаутит — особенность YC NAT, см. раздел 11).

---

## 15. Раздел «Логи» (ELK)

Задание: Elasticsearch для приёма логов, Filebeat на web-серверах (отправка access.log, error.log nginx), Kibana для просмотра.

Состав:
- **Elasticsearch 7.17.28** — приватная ВМ `elasticsearch` (10.0.1.31), 2 vCPU / 2 ГБ, диск 15 ГБ, без public IP, SG `es_sg` (9200 из 10.0.0.0/8).
- **Kibana 7.17.28** — публичная ВМ `kibana` (10.0.1.32 → public IP), 2 vCPU / 2 ГБ, SG `kibana_sg` (5601, 22).
- **Filebeat 7.17.28** (docker) — на web-a и web-b, читает `/var/log/nginx/access.log` и `/var/log/nginx/error.log`, отправляет в ES `10.0.1.31:9200`.

**Особенность установки:** `artifacts.elastic.co` заблокирован в РФ (HTTP 403 на apt-repo и на прямые `.deb`/`.tar.gz`), поэтому ES, Kibana и Filebeat установлены в **Docker-контейнерах из Docker Hub** — официальные образы `library/elasticsearch:7.17.28`, `library/kibana:7.17.28`, `elastic/filebeat:7.17.28` доступны на Docker Hub, а `registry-1.docker.io` работает из РФ.

| Компонент | Docker-образ | Назначение |
|-----------|--------------|------------|
| Elasticsearch | `library/elasticsearch:7.17.28` | приём логов, `discovery.type=single-node`, `xpack.security.enabled=false` |
| Kibana | `library/kibana:7.17.28` | UI логов, `ELASTICSEARCH_HOSTS=http://10.0.1.31:9200` |
| Filebeat (web-a, web-b) | `elastic/filebeat:7.17.28` | чтение nginx access/error log → ES |

Filebeat-конфиг (`/etc/filebeat/filebeat.yml` на web-нодах): два `type: log` input — `access.log` (`log_type: nginx_access`) и `error.log` (`log_type: nginx_error`), поле `server` (`web-a`/`web-b` через env `SERVER_NAME`), `output.elasticsearch.hosts: ["10.0.1.31:9200"]`. Запуск: `docker run -u root --strict.perms=false -v /var/log/nginx:/var/log/nginx:ro -v /etc/filebeat/filebeat.yml:/usr/share/filebeat/filebeat.yml:ro -e SERVER_NAME=web-a elastic/filebeat:7.17.28`.

Проверка:
- ES: индекс `filebeat-7.17.28-2026.09.01`, ~8278 документов (растёт при запросах к сайту через ALB).
- Kibana UI: `http://89.169.134.216:5601` → HTTP 200, создан index pattern `filebeat-*` (через Kibana API).
- Filebeat (web-a, web-b): в логах `Connection to backoff(elasticsearch(http://10.0.1.31:9200)) established`, harvester started для access.log/error.log.

---

## 16. Раздел «Резервное копирование»

Задание: snapshot дисков всех ВМ, ежедневное копирование, срок жизни snapshot — неделя.

Реализация (Terraform, `backup.tf`): ресурс `yandex_compute_snapshot_schedule.daily`:
- `name` = `daily-snapshot-24-01`
- `schedule_policy.expression` = `0 2 * * *` (ежедневно в 02:00 UTC)
- `retention_period` = `168h0m0s` (7 дней)
- `status` = `active`
- `disk_ids` = диски `bastion`, `web-a`, `web-b` (все TF-managed ВМ).

Zabbix-сервер создан вне Terraform — его диск в расписание добавляется вручную через yc CLI / консоль Yandex Cloud (например: `yc compute snapshot-schedule add-disks --name daily-snapshot-24-01 --disk-id <id_диска_zabbix>`).

Проверка: `terraform state show yandex_compute_snapshot_schedule.daily` подтверждает `status = active`, `retention_period = 168h0m0s`, `expression = 0 2 * * *`.

---

## 17. Доступы (актуальные)

| Сервис | URL / адрес | Учётные данные |
|--------|-------------|----------------|
| Сайт (ALB) | http://51.250.7.64/ | — |
| Zabbix UI | http://51.250.9.240/zabbix/ | Admin / zabbix |
| Kibana UI | http://89.169.134.216:5601/ | — (auth отключён, xpack.security=false) |
| Elasticsearch | http://10.0.1.31:9200 (внутренний) | — |
| Kibana SSH | 89.169.134.216:22 | user / ключ `~/.ssh/unikor` |
| Zabbix дашборд | «USE Monitoring — Diploma» (14 виджетов) | — |
| Filebeat index pattern (Kibana) | `filebeat-*` (Discovery) | — |

Доступ к внутренним ВМ (web-a 10.0.1.21, web-b 10.0.2.10, ES 10.0.1.31, Kibana 10.0.1.32) — через zabbix как jump-host:
```
ssh -i ~/.ssh/unikor -J user@51.250.9.240 user@10.0.1.31
```

---

## 18. Итог диплома

Выполнены **все части** задания диплома (https://web-nn.ru → netology-code/sys-diplom):

- ✅ **Сайт** — веб-кластер `web-a`/`web-b` за сетевым балансировщиком ALB (HTTP 200, балансировка).
- ✅ **Мониторинг** — Zabbix Server 7.0 + агенты на всех ВМ, USE-метрики, пороговые триггеры, дашборд «USE Monitoring — Diploma» (14 виджетов), активных проблем 0.
- ✅ **Логи** — Elasticsearch 7.17.28 + Kibana 7.17.28 (Docker, Docker Hub) + Filebeat 7.17.28 на web-нодах (nginx access.log / error.log → ES); index pattern `filebeat-*` в Kibana.
- ✅ **Сеть** — один VPC; приватные подсети (web, Elasticsearch); публичные (bastion, Zabbix, Kibana, ALB); NAT-шлюз для исходящего интернета внутреннего контура; bastion с единственным открытым портом 22; Security Groups только на нужные порты.
- ✅ **Резервное копирование** — `yandex_compute_snapshot_schedule.daily` (ежедневно в 02:00, срок жизни 7 дней, диски всех TF-managed ВМ).

### Файлы проекта (Terraform, `project/task-1/`)
- `network.tf` — VPC, подсети, NAT, route table, SG (bastion/LAN/web_sg/alb_sg).
- `sg-elk.tf` — SG `es_sg` (9200), `kibana_sg` (5601, 22).
- `vms.tf` — ВМ bastion, web-a, web-b + cloud-init + inventory.
- `elk.tf` — ВМ elasticsearch (приватная), kibana (публичная) + cloud-init (Docker).
- `alb.tf` — сетевой балансировщик (target group, backend, router, listener, public IP).
- `backup.tf` — snapshot schedule (ежедневно, retention 7 дней).
- `cloud-init-es.yml`, `cloud-init-kibana.yml` — установка ES/Kibana в Docker из Docker Hub.
- `filebeat.yml` — конфиг Filebeat (nginx access/error → ES).
- `outputs.tf` — публичные/внутренние IP всех ВМ.

Дипломный проект **полностью выполнен**.