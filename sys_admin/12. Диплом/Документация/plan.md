# План действий по созданию сайта и мониторинга

> Дипломный проект — отказоустойчивый веб-кластер за сетевым балансировщиком Yandex Cloud + система мониторинга на базе Zabbix.

---

## Часть 1. Создание сайта (веб-кластер за ALB)

### 1.1. Подготовка инфраструктуры (Terraform)

- [ ] Создать/актуализировать `network.tf`:
  - VPC-сеть `diploma-net` + подсети в зонах A и B.
  - Группа безопасности `web_sg` (80/443 из `alb_sg`, 22 из `10.0.0.0/8`).
  - Группа безопасности `alb_sg` (80/443 из `0.0.0.0/0`).
  - Группа безопасности `zabbix_sg` (80/443 — UI, 22 — SSH, 10051 — приём метрик из `10.0.0.0/8`).
- [ ] Создать `vms.tf` — ВМ:
  - `web-a` (зона A, `10.0.1.21`), `web-b` (зона B, `10.0.2.10`).
  - `bastion` (зона A, публичный IP, NAT-инстанс для доступа).
  - `zabbix` (зона A, `10.0.1.30`, статический внутренний IP, публичный IP `51.250.9.240`).
  - Роли через `cloud-init` (nginx+site, bastion, zabbix, agent).
- [ ] Создать `alb.tf` — сетевой балансировщик (ALB):
  - Target group `web-tg` (web-a:80, web-b:80).
  - Backend group + HTTP router + виртуальный хост (80 → web-tg).
  - ALB Listener (80) с публичным IP `51.250.7.64`.
- [ ] `outputs.tf` — публичные/внутренние IP всех ВМ и ALB.

### 1.2. Развёртывание сайта (cloud-init)

- [ ] `cloud-init-web.yml`:
  - Установка nginx.
  - Разворачивание контента сайта (HTML-страница диплома) в `/var/www/html`.
  - Конфиг nginx с `stub_status` на `location /nginx_status` (allow 10.0.0.0/8).
  - Установка Zabbix Agent 2 + конфиг на `10.0.1.30:10051`.
- [ ] `cloud-init-bastion.yml`:
  - Настройка SSH-доступа, iptables/NAT.
  - Установка Zabbix Agent 2.
- [ ] Применить `terraform apply` (3 added, 3 changed, 1 destroyed).

### 1.3. Проверка сайта

- [ ] ALB (http://51.250.7.64/) → HTTP 200, балансировка между web-a и web-b.
- [ ] Прямой доступ к web-a/web-b по внутреннему IP → HTTP 200.
- [ ] `/nginx_status` на web-a/web-b возвращает stub-status (Active connections, accepts/handled/requests).

---

## Часть 2. Мониторинг (Zabbix)

### 2.1. Развёртывание Zabbix Server

- [ ] `cloud-init-zabbix.yml`:
  - Zabbix Server 7.0 LTS + PostgreSQL 16 + Apache (веб-фронтенд).
  - БД `zabbix` (владелец `zabbix`), импорт схемы.
  - Установка `php-pgsql` (иначе фронтенд не поддерживает PostgreSQL).
  - Zabbix Agent 2 на самом сервере (Server=127.0.0.1).
  - Веб-UI: `/zabbix/`, Admin/zabbix.
- [ ] Проверить http://51.250.9.240/zabbix/ → HTTP 200.

### 2.2. Подключение хостов и агентов

- [ ] Создать хосты в Zabbix (группа `Diploma`):
  - `web-a` (10.0.1.21), `web-b` (10.0.2.10), `bastion`, `zabbix` (127.0.0.1).
- [ ] Линковать шаблоны:
  - `Linux by Zabbix agent` — все хосты.
  - `Nginx by Zabbix agent` — web-a, web-b.
- [ ] Установить Zabbix Agent 2 на web-a, web-b, bastion (если не встал через cloud-init — вручную).
- [ ] Настроить агенты: `Server=10.0.1.30`, `ServerActive=10.0.1.30:10051`, `Hostname=` имя хоста.
- [ ] Дождаться статуса `available=1` для всех 4 хостов.

### 2.3. Сбор метрик по методологии USE

**Utilization (утилизация):**
- [ ] CPU: `system.cpu.load`, CPU utilization (Linux template).
- [ ] RAM: `vm.memory.size[available]` (свободно ~686 МБ).
- [ ] Диск: `vda: Disk utilization and queue`, `FS / space`.

**Saturation (насыщение):**
- [ ] Сеть: `Interface eth0: Network traffic` (входящий/исходящий трафик, ошибки).
- [ ] Диск: queue length (Linux template).

**Errors (ошибки):**
- [ ] HTTP: `HTTP service status` (net.tcp.service[http]), `HTTP response time`.
- [ ] Nginx: `nginx.requests.total`, `nginx.requests.total.rate`, `nginx.connections.*` (active/reading/writing/waiting).
- [ ] Nginx stub_status: `/nginx_status` (Active connections, accepts/handled/requests).

### 2.4. Настройка триггеров (пороги)

- [ ] Linux template:
  - High CPU utilization (>90%).
  - High CPU load.
  - Lack of free memory.
  - Low disk space (<10%).
  - High network error rate.
- [ ] HTTP:
  - `HTTP service down` (priority High).
  - `HTTP response time > 1s` (priority Average).
- [ ] Nginx:
  - `Failed to fetch stub status page`.
  - `Nginx: Service is down`.

### 2.5. Дашборд «USE Monitoring — Diploma» (ID 401)

- [ ] Создать через `zbx-dashboard.sh` (dashboard.create, структура `pages → widgets`).
- [ ] 14 виджетов:
  - Problems / Thresholds (USE).
  - web-a / web-b: CPU utilization, Memory usage, Network eth0, Disk vda, FS / space, Nginx req/s, HTTP response time.
- [ ] Проверить: `dashboard.get` → `widgets | length` = 14.

### 2.6. Финальная проверка мониторинга

- [ ] Все 4 хоста `available=1` (агенты шлют метрики).
- [ ] Nginx-метрики идут: `nginx.requests.total` растёт, `nginx.requests.total.rate` > 0.
- [ ] HTTP-метрики: service UP, response time < 1s.
- [ ] Активные проблемы (`problem.get recent=false`) = **0**.
- [ ] Дашборд отображает графики USE по web-узлам.

---

## Часть 3. Документирование и сдача

- [ ] Записать доступы:
  - Zabbix UI: **http://51.250.9.240/zabbix/** (Admin / zabbix).
  - Сайт: **http://51.250.7.64/** (HTTP 200, балансировка web-a/web-b).
- [ ] Описать архитектуру (схема: ALB → web-a/web-b; Zabbix → агенты на всех ВМ).
- [ ] Описать известные особенности:
  - Bastion внешний 22 недоступен (таймаут) — доступ к внутренним ВМ через zabbix как jump-host.
  - Агенты на web/bastion установлены вручную при действующих ВМ; в `.tf` cloud-init прописан декларативно (автоприменение при пересоздании).
- [ ] Сформировать итоговый отчёт диплома.

---

## Статус

| Блок | Статус |
|------|--------|
| Веб-кластер + ALB | ✅ Готово |
| Zabbix Server | ✅ Готово |
| Агенты на всех ВМ | ✅ Готово |
| USE-метрики (CPU/RAM/Disk/Net/HTTP) | ✅ Готово |
| Nginx stub_status + метрики | ✅ Готово |
| Триггеры (пороги) | ✅ Готово |
| Дашборд USE (14 виджетов) | ✅ Готово |
| Активные проблемы | ✅ 0 |
| Документация (мониторинг) | ✅ Готово |
| Раздел «Сеть» (VPC/приватные подсети/NAT/bastion/SG) | ✅ Готово |
| Раздел «Логи» (Elasticsearch + Kibana + Filebeat) | ✅ Готово |
| Раздел «Резервное копирование» (snapshot schedule) | ✅ Готово |
| Документация (все разделы диплома) | ✅ Готово (info.md, разделы 14–18) |

> Все части задания диплома (https://web-nn.ru → netology-code/sys-diplom) выполнены.
> Подробности — в `info.md`, разделы 14 (Сеть), 15 (Логи/ELK), 16 (Резервное копирование), 17 (Доступы), 18 (Итог).