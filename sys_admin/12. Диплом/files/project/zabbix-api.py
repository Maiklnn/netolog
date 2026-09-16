#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Настройка Zabbix 7.0 через API:
  * группы узлов и узлы сети (агенты адресуются по внутренним FQDN);
  * шаблон метрик nginx (USE для HTTP: запросы, соединения, ошибки 4xx/5xx);
  * пороги (триггеры) — они же линии порогов на графиках;
  * классические графики по принципу USE для CPU, RAM, дисков, сети, HTTP;
  * дашборды с этими графиками.

Скрипт идемпотентный: перед созданием объект ищется по имени/ключу.
Запускается на самой ВМ с Zabbix-сервером (localhost).
"""
import json
import sys
import time
import urllib.request
import urllib.error

API_URL = "http://127.0.0.1/api_jsonrpc.php"
API_USER = "Admin"
API_PASSWORD = "zabbix"

# Внутренние FQDN виртуальных машин в зоне ru-central1.internal
HOSTS = [
    {
        "host": "bastion",
        "name": "bastion — точка входа (SSH)",
        "dns": "bastion.ru-central1.internal",
        "groups": ["Linux servers"],
        "templates": ["Linux by Zabbix agent"],
        "graphs": True,
    },
    {
        "host": "zabbix",
        "name": "zabbix — сервер мониторинга",
        "dns": "zabbix.ru-central1.internal",
        "groups": ["Linux servers"],
        "templates": ["Linux by Zabbix agent"],
        "graphs": True,
    },
    {
        "host": "web-a",
        "name": "web-a — веб-сервер (зона ru-central1-a)",
        "dns": "web-a.ru-central1.internal",
        "groups": ["Linux servers", "Web servers"],
        "templates": ["Linux by Zabbix agent", "Nginx USE by Zabbix agent"],
        "graphs": True,
    },
    {
        "host": "web-b",
        "name": "web-b — веб-сервер (зона ru-central1-b)",
        "dns": "web-b.ru-central1.internal",
        "groups": ["Linux servers", "Web servers"],
        "templates": ["Linux by Zabbix agent", "Nginx USE by Zabbix agent"],
        "graphs": True,
    },
    {
        "host": "elasticsearch",
        "name": "elasticsearch — хранилище журналов (ELK)",
        "dns": "elasticsearch.ru-central1.internal",
        "groups": ["Linux servers"],
        "templates": ["Linux by Zabbix agent"],
        "graphs": True,
    },
    {
        "host": "kibana",
        "name": "kibana — веб-интерфейс журналов (ELK)",
        "dns": "kibana.ru-central1.internal",
        "groups": ["Linux servers"],
        "templates": ["Linux by Zabbix agent"],
        "graphs": True,
    },
]

NGINX_TEMPLATE = "Nginx USE by Zabbix agent"
NET_IF = "eth0"          # имя сетевого интерфейса на ВМ
FS_MOUNT = "/"           # контролируемый раздел диска

# Ключи элементов данных штатного шаблона «Linux by Zabbix agent» в Zabbix 7.0.
# Проверено запросом item.get: имена ключей в 7.0 отличаются от старых версий
# (vm.memory.util вместо vm.memory.utilization, vfs.fs.dependent.size вместо
# vfs.fs.size, имя интерфейса в ключах сети берётся в кавычках).
MEM_UTIL = "vm.memory.util"                          # утилизация RAM, %
MEM_AVAIL = "vm.memory.size[pavailable]"             # доступная RAM, %
SWAP_PFREE = "system.swap.size[,pfree]"              # свободный swap, %
FS_PUSED = "vfs.fs.dependent.size[%s,pused]" % FS_MOUNT   # занято на разделе, %
NET_IN = 'net.if.in["%s"]' % NET_IF                  # приём, бит/с
NET_OUT = 'net.if.out["%s"]' % NET_IF                # передача, бит/с
NET_ERR_IN = 'net.if.in["%s",errors]' % NET_IF       # ошибки приёма
NET_ERR_OUT = 'net.if.out["%s",errors]' % NET_IF     # ошибки передачи
NET_DROP_IN = 'net.if.in["%s",dropped]' % NET_IF     # потери приёма
DISK_UTIL = "vfs.dev.util[vda]"                      # утилизация диска, %
DISK_READ = "vfs.dev.read.rate[vda]"                 # чтение, операций/с
DISK_WRITE = "vfs.dev.write.rate[vda]"               # запись, операций/с

_id = 0


def api(method, params=None, auth=None):
    """Вызов метода Zabbix API."""
    global _id
    _id += 1
    payload = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": _id}
    if auth:
        payload["auth"] = auth
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json-rpc"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as err:
        sys.exit("Не удалось обратиться к Zabbix API (%s): %s" % (API_URL, err))
    if "error" in data:
        err = data["error"]
        raise RuntimeError("%s: %s — %s" % (method, err.get("message"), err.get("data")))
    return data["result"]


def one(result, field, value):
    """Первый объект из ответа API с заданным значением поля."""
    for obj in result:
        if obj.get(field) == value:
            return obj
    return None


# ---------------------------------------------------------------- группы и узлы

def ensure_host_group(auth, name):
    found = one(api("hostgroup.get", {"filter": {"name": [name]}}, auth), "name", name)
    if found:
        return found["groupid"]
    res = api("hostgroup.create", {"name": name}, auth)
    print("  + группа узлов «%s»" % name)
    return res["groupids"][0]


def ensure_template_group(auth, name):
    # В Zabbix 6.2+ группа шаблонов — отдельная сущность (templategroup);
    # группа узлов (hostgroup) для шаблона не подходит, API отвечает
    # "Invalid parameter /1/groups/1: object does not exist".
    found = one(api("templategroup.get", {"filter": {"name": [name]}}, auth), "name", name)
    if found:
        return found["groupid"]
    res = api("templategroup.create", {"name": name}, auth)
    print("  + группа шаблонов «%s»" % name)
    return res["groupids"][0]


def ensure_template(auth, name, group_name):
    found = one(api("template.get", {"filter": {"host": [name]}}, auth), "host", name)
    if found:
        return found["templateid"]
    group = ensure_template_group(auth, group_name)
    res = api("template.create", {"host": name, "groups": [{"groupid": group}]}, auth)
    print("  + шаблон «%s»" % name)
    return res["templateids"][0]


def ensure_template_item(auth, templateid, item):
    found = one(api("item.get", {"hostids": [templateid], "filter": {"key_": [item["key_"]]}}, auth),
                "key_", item["key_"])
    if found:
        return found["itemid"]
    params = dict(item)
    params["hostid"] = templateid
    res = api("item.create", params, auth)
    print("  + элемент данных «%s»" % item["name"])
    return res["itemids"][0]


def ensure_template_trigger(auth, templateid, description, expression, priority, comments=""):
    found = one(api("trigger.get", {"hostids": [templateid], "filter": {"description": [description]}}, auth),
                "description", description)
    if found:
        return found["triggerid"]
    res = api("trigger.create", {
        "description": description,
        "expression": expression,
        "priority": priority,
        "comments": comments,
    }, auth)
    print("  + порог «%s»" % description)
    return res["triggerids"][0]


def ensure_host(auth, spec, groups_ids, template_ids):
    found = one(api("host.get", {"filter": {"host": [spec["host"]]}}, auth), "host", spec["host"])
    if found:
        hostid = found["hostid"]
    else:
        res = api("host.create", {
            "host": spec["host"],
            "name": spec["name"],
            "groups": [{"groupid": g} for g in groups_ids],
            "templates": [{"templateid": t} for t in template_ids],
            "interfaces": [{
                "type": 1,          # интерфейс Zabbix agent
                "main": 1,
                "useip": 0,         # подключаться по DNS-имени, а не по IP
                "ip": "",
                "dns": spec["dns"],
                "port": "10050",
            }],
            "inventory_mode": -1,
        }, auth)
        hostid = res["hostids"][0]
        print("  + узел сети «%s» (%s)" % (spec["host"], spec["dns"]))
    # досыпаем группы/шаблоны, если узел уже был создан ранее
    api("host.update", {
        "hostid": hostid,
        "groups": [{"groupid": g} for g in groups_ids],
        "templates": [{"templateid": t} for t in template_ids],
    }, auth)
    return hostid


def ensure_host_trigger(auth, hostid, host_name, description, expression, priority, comments=""):
    found = one(api("trigger.get", {"hostids": [hostid], "filter": {"description": [description]}}, auth),
                "description", description)
    if found:
        return found["triggerid"]
    res = api("trigger.create", {
        "description": description,
        "expression": expression,
        "priority": priority,
        "comments": comments,
    }, auth)
    print("  + порог у %s: «%s»" % (host_name, description))
    return res["triggerids"][0]


# ------------------------------------------------------------------- метрики

def find_items(auth, hostid, search):
    """Элементы данных узла, у которых ключ начинается с search."""
    items = api("item.get", {
        "hostids": [hostid],
        "search": {"key_": search},
        "searchByAny": True,
        "output": ["itemid", "name", "key_", "units", "value_type"],
        "sortfield": "key_",
    }, auth)
    return [i for i in items if i["key_"].startswith(search)]


def pick_item(auth, hostid, key_variants):
    """Первый существующий элемент данных из списка вариантов ключа."""
    for key in key_variants:
        items = [i for i in api("item.get", {"hostids": [hostid], "filter": {"key_": [key]}}, auth)
                 if i["key_"] == key]
        if items:
            return items[0]
    return None


def run_discovery_now(auth, hostid, keys):
    """Принудительно запускает правила обнаружения (task.create, тип 6 — «выполнить сейчас»).

    Элементы данных диска и сетевых интерфейсов в шаблоне «Linux by Zabbix agent»
    создаются обнаружением, а его штатный интервал — 1 час. Без принудительного
    запуска графики диска и сети у только что созданных узлов не создаются.
    """
    for key in keys:
        for rule in api("discoveryrule.get", {"hostids": [hostid], "filter": {"key_": [key]}}, auth):
            try:
                api("task.create", {"type": 6, "request": {"itemid": rule["itemid"]}}, auth)
            except RuntimeError as err:
                print("      правило %s не запущено: %s" % (key, err))


def wait_items(auth, hostid, keys, attempts=20, pause=3):
    """Ждёт появления элементов данных, возвращает True, если все появились."""
    for _ in range(attempts):
        if all(pick_item(auth, hostid, [k]) for k in keys):
            return True
        time.sleep(pause)
    return False


def ensure_graph(auth, hostid, name, gitems):
    """Классический график узла. gitems: список (itemid, цвет)."""
    found = one(api("graph.get", {"hostids": [hostid], "filter": {"name": [name]}}, auth), "name", name)
    if found:
        return found["graphid"]
    items = []
    for order, (itemid, color) in enumerate(gitems):
        items.append({
            "itemid": itemid,
            "color": color,
            "drawtype": 0,
            "sortorder": order,
            "yaxisside": 0,
        })
    res = api("graph.create", {
        "name": name,
        "width": 900,
        "height": 300,
        "graphtype": 0,
        "show_legend": 1,
        "show_work_period": 0,
        "show_triggers": 1,     # рисует линии порогов на графике
        # В Zabbix 6.0+ список элементов графика передаётся в параметре gitems;
        # со старым именем items API отвечает «Missing items for graph».
        "gitems": items,
    }, auth)
    return res["graphids"][0]


# ------------------------------------------------------------------ дашборды

def ensure_dashboard(auth, name, widgets):
    found = one(api("dashboard.get", {"filter": {"name": [name]}}, auth), "name", name)
    if found:
        return found["dashboardid"]
    res = api("dashboard.create", {
        "name": name,
        "display_period": 30,
        "auto_start": 1,
        "pages": [{"name": "Обзор", "widgets": widgets}],
    }, auth)
    print("  + дашборд «%s»" % name)
    return res["dashboardids"][0]


def graph_widget(name, x, y, w, h, graphid):
    return {
        "type": "graph",
        "name": name,
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "fields": [
            {"type": 0, "name": "source", "value": "0"},
            {"type": 6, "name": "graphid", "value": str(graphid)},
        ],
    }


def problems_widget(name, x, y, w, h):
    return {
        "type": "problems",
        "name": name,
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "fields": [
            {"type": 0, "name": "show", "value": "3"},
            {"type": 0, "name": "show_tags", "value": "1"},
        ],
    }


# ----------------------------------------------------------------------- main

def main():
    print("Подключение к Zabbix API %s" % API_URL)
    auth = api("user.login", {"username": API_USER, "password": API_PASSWORD})
    print("Авторизация выполнена (пользователь %s)\n" % API_USER)

    print("Группы узлов:")
    groups = {}
    for g in ["Linux servers", "Web servers"]:
        groups[g] = ensure_host_group(auth, g)

    print("\nШаблон метрик nginx (USE для HTTP):")
    nginx_tpl = ensure_template(auth, NGINX_TEMPLATE, "Templates/Web servers")
    common = {"type": 0, "value_type": 3, "delay": "60s", "history": "7d", "trends": "90d"}
    # Зависимый элемент данных (type 18) пересчитывает счётчик в скорость.
    # В Zabbix 7.0 у шага предобработки обязательны поля error_handler и
    # error_handler_params — без них API отвечает «the parameter "error_handler" is missing».
    rate = {"type": 18, "value_type": 0, "delay": "0", "history": "7d", "trends": "90d",
            "preprocessing": [{"type": 10, "params": "",
                               "error_handler": 0, "error_handler_params": ""}]}  # 10 = изменение в секунду

    nginx_items = [
        (dict(common, key_="nginx.status.active", name="Nginx: активных соединений"),
         None, "соединения"),
        (dict(common, key_="nginx.status.requests", name="Nginx: всего запросов"),
         "nginx.status.requests.rate", "запросы"),
        (dict(common, key_="nginx.status.reading", name="Nginx: соединений на чтение"),
         None, "соединения"),
        (dict(common, key_="nginx.status.writing", name="Nginx: соединений на запись"),
         None, "соединения"),
        (dict(common, key_="nginx.status.waiting", name="Nginx: соединений в ожидании"),
         None, "соединения"),
        (dict(common, key_="nginx.http.log.4xx", name="Nginx: ответов 4xx (всего)"),
         "nginx.http.log.4xx.rate", "ошибки"),
        (dict(common, key_="nginx.http.log.5xx", name="Nginx: ответов 5xx (всего)"),
         "nginx.http.log.5xx.rate", "ошибки"),
    ]

    item_ids = {}
    for item, rate_key, _group in nginx_items:
        item_ids[item["key_"]] = ensure_template_item(auth, nginx_tpl, item)
        if rate_key:
            rate_item = dict(rate, key_=rate_key,
                             name=item["name"].replace("(всего)", "в секунду"),
                             master_itemid=item_ids[item["key_"]])
            item_ids[rate_key] = ensure_template_item(auth, nginx_tpl, rate_item)

    print("\nПороги (триггеры) для HTTP-метрик:")
    ensure_template_trigger(
        auth, nginx_tpl, "Nginx: нет данных stub_status",
        "nodata(/Nginx USE by Zabbix agent/nginx.status.active,5m)=1", 2,
        "nginx не отдаёт статистику — проверьте stub_status и агент")
    ensure_template_trigger(
        auth, nginx_tpl, "Nginx: доля ошибок 5xx выше порога (1 в секунду)",
        "avg(/Nginx USE by Zabbix agent/nginx.http.log.5xx.rate,5m)>1", 4,
        "Более 1 ответа 5xx в секунду в среднем за 5 минут")
    ensure_template_trigger(
        auth, nginx_tpl, "Nginx: ответов 4xx больше 10 в секунду",
        "avg(/Nginx USE by Zabbix agent/nginx.http.log.4xx.rate,5m)>10", 2,
        "Много клиентских ошибок — возможен скан или битые ссылки")
    ensure_template_trigger(
        auth, nginx_tpl, "Nginx: высокая нагрузка (больше 100 запросов в секунду)",
        "avg(/Nginx USE by Zabbix agent/nginx.status.requests.rate,5m)>100", 2,
        "Насыщение веб-сервера по запросам")
    ensure_template_trigger(
        auth, nginx_tpl, "Nginx: количество активных соединений больше 100",
        "avg(/Nginx USE by Zabbix agent/nginx.status.active,5m)>100", 2,
        "Насыщение по одновременным соединениям")

    print("\nУзлы сети:")
    host_ids = {}
    for spec in HOSTS:
        template_ids = []
        for tpl_name in spec["templates"]:
            if tpl_name == NGINX_TEMPLATE:
                template_ids.append(nginx_tpl)
            else:
                found = one(api("template.get", {"filter": {"host": [tpl_name]}}, auth), "host", tpl_name)
                if not found:
                    raise RuntimeError("не найден штатный шаблон «%s»" % tpl_name)
                template_ids.append(found["templateid"])
        host_ids[spec["host"]] = ensure_host(auth, spec, [groups[g] for g in spec["groups"]], template_ids)

    # Элементы данных диска и сетевых интерфейсов создаются обнаружением
    # (штатный интервал — 1 час), поэтому для новых узлов запускаем его сразу.
    print("\nПодготовка метрик диска и сети:")
    needed = (FS_PUSED, NET_IN, DISK_UTIL)
    for spec in HOSTS:
        h = spec["host"]
        hid = host_ids[h]
        if all(pick_item(auth, hid, [k]) for k in needed):
            print("  %s: метрики диска и сети уже есть" % h)
            continue
        print("  %s: запускаю обнаружение файловых систем, интерфейсов и дисков" % h)
        run_discovery_now(auth, hid, ["vfs.fs.dependent.discovery", "vfs.fs.discovery",
                                      "net.if.discovery", "vfs.dev.discovery"])
        if wait_items(auth, hid, needed):
            print("  %s: метрики диска и сети появились" % h)
        else:
            print("  %s: метрики ещё не появились — графики диска и сети создадутся "
                  "при повторном запуске" % h)

    print("\nПороги (триггеры) для CPU, памяти, диска и сети:")
    for spec in HOSTS:
        h = spec["host"]
        hid = host_ids[h]
        util = pick_item(auth, hid, ["system.cpu.util"])
        mem = pick_item(auth, hid, [MEM_UTIL, "vm.memory.utilization"])
        fs = pick_item(auth, hid, [FS_PUSED, "vfs.fs.size[/,pused]"])
        net_in = pick_item(auth, hid, [NET_ERR_IN])
        net_out = pick_item(auth, hid, [NET_ERR_OUT])

        if util:
            ensure_host_trigger(auth, hid, h, "CPU: загрузка выше 80% (5 минут)",
                                "avg(/%s/system.cpu.util,5m)>80" % h, 2,
                                "Порог предупреждения по утилизации CPU")
            ensure_host_trigger(auth, hid, h, "CPU: загрузка выше 95% (5 минут)",
                                "avg(/%s/system.cpu.util,5m)>95" % h, 4,
                                "Критическая утилизация CPU")
        if mem:
            ensure_host_trigger(auth, hid, h, "Память: использовано более 85%",
                                "avg(/%s/%s,5m)>85" % (h, MEM_UTIL), 2,
                                "Порог по утилизации оперативной памяти")
            ensure_host_trigger(auth, hid, h, "Память: использовано более 95%",
                                "avg(/%s/%s,5m)>95" % (h, MEM_UTIL), 4,
                                "Критическая утилизация оперативной памяти")
        if fs:
            ensure_host_trigger(auth, hid, h, "Диск %s: занято более 85%%" % FS_MOUNT,
                                "last(/%s/%s)>85" % (h, FS_PUSED), 2,
                                "Порог по заполнению диска")
            ensure_host_trigger(auth, hid, h, "Диск %s: занято более 95%%" % FS_MOUNT,
                                "last(/%s/%s)>95" % (h, FS_PUSED), 4,
                                "Критическое заполнение диска")
        if net_in:
            ensure_host_trigger(auth, hid, h, "Сеть: ошибки приёма на %s" % NET_IF,
                                "last(/%s/%s)>0" % (h, NET_ERR_IN), 2,
                                "Ошибки на входящем трафике интерфейса")
        if net_out:
            ensure_host_trigger(auth, hid, h, "Сеть: ошибки передачи на %s" % NET_IF,
                                "last(/%s/%s)>0" % (h, NET_ERR_OUT), 2,
                                "Ошибки на исходящем трафике интерфейса")

    print("\nГрафики USE по узлам:")
    graphs = {}
    for spec in HOSTS:
        h = spec["host"]
        hid = host_ids[h]
        g = {}

        # --- CPU: утилизация и насыщение (load average) ---
        cpu_util = pick_item(auth, hid, ["system.cpu.util"])
        load1 = pick_item(auth, hid, ["system.cpu.load[all,avg1]"])
        load5 = pick_item(auth, hid, ["system.cpu.load[all,avg5]"])
        gitems = []
        if cpu_util:
            gitems.append((cpu_util["itemid"], "D20000"))
        if load1:
            gitems.append((load1["itemid"], "0050D0"))
        if load5:
            gitems.append((load5["itemid"], "00A0A0"))
        if gitems:
            g["cpu"] = ensure_graph(auth, hid, "USE CPU: загрузка и load average", gitems)

        # --- CPU: насыщение и «ошибки» (переключения контекста, прерывания) ---
        sw = pick_item(auth, hid, ["system.cpu.switches"])
        intr = pick_item(auth, hid, ["system.cpu.intr"])
        gitems = []
        if sw:
            gitems.append((sw["itemid"], "8A2BE2"))
        if intr:
            gitems.append((intr["itemid"], "FF8C00"))
        if gitems:
            g["cpu_sat"] = ensure_graph(auth, hid, "USE CPU: переключения контекста и прерывания", gitems)

        # --- RAM: утилизация и насыщение (доступная память, swap) ---
        mem_util = pick_item(auth, hid, [MEM_UTIL, "vm.memory.utilization"])
        mem_avail = pick_item(auth, hid, [MEM_AVAIL, "vm.memory.available"])
        swap = pick_item(auth, hid, [SWAP_PFREE, "system.swap.size[,pused]"])
        gitems = []
        if mem_util:
            gitems.append((mem_util["itemid"], "C00000"))
        if mem_avail:
            gitems.append((mem_avail["itemid"], "00A000"))
        if swap:
            gitems.append((swap["itemid"], "FFA500"))
        if gitems:
            g["ram"] = ensure_graph(auth, hid, "USE RAM: память и swap", gitems)

        # --- Диск: заполнение и скорость обмена ---
        fs_pused = pick_item(auth, hid, [FS_PUSED, "vfs.fs.size[/,pused]"])
        gitems = []
        if fs_pused:
            gitems.append((fs_pused["itemid"], "C00000"))
        if gitems:
            g["disk_space"] = ensure_graph(auth, hid, "USE Диск %s: заполнение" % FS_MOUNT, gitems)

        # Утилизация диска (util) + операции чтения/записи в секунду
        dev_util = pick_item(auth, hid, [DISK_UTIL])
        dev_read = pick_item(auth, hid, [DISK_READ])
        dev_write = pick_item(auth, hid, [DISK_WRITE])
        gitems = []
        if dev_read:
            gitems.append((dev_read["itemid"], "0050D0"))
        if dev_write:
            gitems.append((dev_write["itemid"], "D20000"))
        if gitems:
            g["disk_io"] = ensure_graph(auth, hid, "USE Диск: операции чтения и записи", gitems)
        gitems = []
        if dev_util:
            gitems.append((dev_util["itemid"], "C00000"))
        if gitems:
            g["disk_util"] = ensure_graph(auth, hid, "USE Диск: утилизация (util)", gitems)

        # --- Сеть: трафик, ошибки и потери ---
        net_in = pick_item(auth, hid, [NET_IN])
        net_out = pick_item(auth, hid, [NET_OUT])
        gitems = []
        if net_in:
            gitems.append((net_in["itemid"], "00A000"))
        if net_out:
            gitems.append((net_out["itemid"], "0050D0"))
        if gitems:
            g["net"] = ensure_graph(auth, hid, "USE Сеть %s: трафик" % NET_IF, gitems)

        net_err_in = pick_item(auth, hid, [NET_ERR_IN])
        net_err_out = pick_item(auth, hid, [NET_ERR_OUT])
        net_dr_in = pick_item(auth, hid, [NET_DROP_IN])
        gitems = []
        if net_err_in:
            gitems.append((net_err_in["itemid"], "C00000"))
        if net_err_out:
            gitems.append((net_err_out["itemid"], "8A2BE2"))
        if net_dr_in:
            gitems.append((net_dr_in["itemid"], "FFA500"))
        if gitems:
            g["net_err"] = ensure_graph(auth, hid, "USE Сеть %s: ошибки и потери" % NET_IF, gitems)

        # --- HTTP: только для веб-серверов ---
        if NGINX_TEMPLATE in spec["templates"]:
            req_rate = pick_item(auth, hid, ["nginx.status.requests.rate"])
            req_total = pick_item(auth, hid, ["nginx.status.requests"])
            gitems = []
            if req_rate:
                gitems.append((req_rate["itemid"], "00A000"))
            if req_total:
                gitems.append((req_total["itemid"], "0050D0"))
            if gitems:
                g["http_util"] = ensure_graph(auth, hid, "USE HTTP: запросы", gitems)

            conn = []
            for key, color in (("nginx.status.active", "C00000"),
                               ("nginx.status.reading", "00A000"),
                               ("nginx.status.writing", "0050D0"),
                               ("nginx.status.waiting", "FFA500")):
                it = pick_item(auth, hid, [key])
                if it:
                    conn.append((it["itemid"], color))
            if conn:
                g["http_conn"] = ensure_graph(auth, hid, "USE HTTP: соединения", conn)

            err = []
            for key, color in (("nginx.http.log.4xx.rate", "FFA500"),
                               ("nginx.http.log.5xx.rate", "C00000")):
                it = pick_item(auth, hid, [key])
                if it:
                    err.append((it["itemid"], color))
            if err:
                g["http_err"] = ensure_graph(auth, hid, "USE HTTP: ошибки 4xx и 5xx", err)

        graphs[h] = g
        print("  %s: создано графиков — %d" % (h, len(g)))

    print("\nДашборды:")
    # Дашборд 1: обзор USE по всем ВМ
    widgets = [problems_widget("Текущие проблемы", 0, 0, 24, 4)]
    x, y = 0, 4
    for spec in HOSTS:
        h = spec["host"]
        for key, title in (("cpu", "CPU"), ("ram", "RAM"), ("cpu_sat", "CPU насыщение"),
                           ("disk_space", "Диск"), ("disk_io", "Диск операции"),
                           ("net", "Сеть"), ("net_err", "Сеть ошибки")):
            gid = graphs[h].get(key)
            if not gid:
                continue
            widgets.append(graph_widget("%s — %s" % (title, h), x, y, 12, 5, gid))
            x += 12
            if x >= 24:
                x = 0
                y += 5
    ensure_dashboard(auth, "USE: хосты (CPU, RAM, диск, сеть)", widgets)

    # Дашборд 2: веб-серверы — HTTP-метрики
    widgets = [problems_widget("Проблемы веб-серверов", 0, 0, 24, 4)]
    x, y = 0, 4
    for spec in HOSTS:
        h = spec["host"]
        if NGINX_TEMPLATE not in spec["templates"]:
            continue
        for key, title in (("http_util", "HTTP запросы"),
                           ("http_conn", "HTTP соединения"),
                           ("http_err", "HTTP ошибки")):
            gid = graphs[h].get(key)
            if not gid:
                continue
            widgets.append(graph_widget("%s — %s" % (title, h), x, y, 12, 5, gid))
            x += 12
            if x >= 24:
                x = 0
                y += 5
    ensure_dashboard(auth, "USE: веб-серверы (HTTP)", widgets)

    print("\nГотово. Узлов: %d, графиков: %d" % (len(host_ids),
                                                sum(len(g) for g in graphs.values())))


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        sys.exit("Ошибка API: %s" % exc)
