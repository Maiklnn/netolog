#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сборщик workflow «Агент визуальных креативов» для n8n 2.8.4.

Читает JS-код узлов из tools/*.js и системный промпт агента из
tools/00-agent-system.md, подставляет их в JSON workflow и записывает
результат в workflow-visual-creatives.json.

Запуск:  python build-workflow.py
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "tools")
OUT = os.path.join(HERE, "workflow-visual-creatives.json")

OLLAMA_CRED = {"id": "DEHgfM1I0ZJBmGoo", "name": "Ollama (10.0.2.2:11434)"}
MODEL = "deepseek-v4.1-flash:cloud"
DATA_DIR = "/var/lib/n8n/.n8n-files/visual-creatives"
OLLAMA_URL = "http://10.0.2.2:11434"

PREFIX = "c1000000-0000-4000-8000-0000000000"


def nid(n):
    return PREFIX + "%02d" % n


def read(name):
    with open(os.path.join(TOOLS, name), encoding="utf-8") as f:
        return f.read()


def code_node(name, num, js, position, notes=None):
    return {
        "parameters": {"mode": "runOnceForAllItems", "jsCode": js},
        "id": nid(num),
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
        "notes": notes or "",
    }


def read_file_node(name, num, path, position, notes=None):
    return {
        "parameters": {"operation": "read", "fileSelector": path, "options": {}},
        "id": nid(num),
        "name": name,
        "type": "n8n-nodes-base.readWriteFile",
        "typeVersion": 1,
        "position": position,
        "notes": notes or "",
    }


def write_file_node(name, num, file_name_expr, position, notes=None):
    return {
        "parameters": {
            "operation": "write",
            # "=" в начале делает значение выражением n8n
            "fileName": "=" + file_name_expr,
            "dataPropertyName": "data",
            "options": {},
        },
        "id": nid(num),
        "name": name,
        "type": "n8n-nodes-base.readWriteFile",
        "typeVersion": 1,
        "position": position,
        "notes": notes or "",
    }


def text_node(name, num, position, notes=None):
    return {
        "parameters": {"operation": "text", "binaryPropertyName": "data",
                       "destinationKey": "data", "options": {}},
        "id": nid(num),
        "name": name,
        "type": "n8n-nodes-base.extractFromFile",
        "typeVersion": 1,
        "position": position,
        "notes": notes or "",
    }


def download_node(name, num, position, notes=None):
    """HTTP Request, который кладёт ответ в binary: только так на этом n8n
    получаются настоящие байты картинки (Code-узел калечит бинарники)."""
    return {
        "parameters": {
            "method": "GET",
            "url": "={{ $json.image_url }}",
            "options": {
                "response": {
                    "response": {
                        "responseFormat": "file",
                        "outputPropertyName": "data",
                    }
                },
                "timeout": 300000,
            },
        },
        "id": nid(num),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": position,
        "notes": notes or "",
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 5000,
    }


def has_url_node(name, num, position, notes=None):
    """Ветвление: быстрый генератор отдал ссылку — скачиваем HTTP-узлом,
    запасной отдал base64 — собираем бинарник Code-узлом."""
    return {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose",
                            "version": 2},
                "conditions": [
                    {
                        "id": "has-url-1",
                        "leftValue": "={{ $json.image_url }}",
                        "rightValue": "",
                        "operator": {"type": "string", "operation": "notEmpty", "singleValue": True},
                    }
                ],
                "combinator": "and",
            },
            "looseTypeValidation": True,
            "options": {},
        },
        "id": nid(num),
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": position,
        "notes": notes or "",
    }


def vision_node(name, num, position, notes=None):
    return {
        "parameters": {
            "method": "POST",
            "url": OLLAMA_URL + "/api/generate",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": ("={{ { model: $json.ollama_model, prompt: $json.vision_prompt,"
                         " images: [$json.image_b64], stream: false, format: 'json',"
                         " options: { temperature: $json.vision_temperature } } }}"),
            "options": {"timeout": 600000},
        },
        "id": nid(num),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": position,
        "notes": notes or "",
        "onError": "continueRegularOutput",
        # Облачная Ollama иногда отвечает 500 «Internal Server Error» на свою же
        # внутреннюю ошибку — в прогоне 85 так потерялась оценка V4. Двух попыток
        # с паузой 3 с не хватило, поэтому попыток больше и пауза длиннее.
        "retryOnFail": True,
        "maxTries": 4,
        "waitBetweenTries": 8000,
    }


def main():
    system_prompt = read("00-agent-system.md").strip()

    js = {
        "input": read("01-input.js"),
        "parse": read("02-parse-brief.js"),
        "prompts": read("03-build-prompts.js"),
        "generate": read("04-generate.js"),
        "img_from_b64": read("04b-image-from-b64.js"),
        "vision_req": read("05-vision-request.js"),
        "checklist_1": read("06-checklist.js").replace("__SRC__", "Собрать запрос к Vision"),
        "checklist_2": read("06-checklist.js").replace("__SRC__", "Собрать запрос к Vision (правка)"),
        "fix": read("07-fix-prompt.js"),
        "registry": read("08-registry.js"),
        "final": read("09-final.js"),
    }

    nodes = [
        # --- ТРИГГЕРЫ -------------------------------------------------------
        {
            "parameters": {},
            "id": nid(1),
            "name": "Запуск вручную (кнопка)",
            "type": "n8n-nodes-base.manualTrigger",
            "typeVersion": 1,
            "position": [-1240, 200],
            "notes": "Ручной запуск из интерфейса n8n кнопкой «Execute workflow».",
        },

        {
            "parameters": {
                "httpMethod": "POST",
                "path": "visual-creatives",
                "responseMode": "lastNode",
                "options": {},
            },
            "id": nid(2),
            "name": "Запуск по ссылке (Webhook)",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2,
            "position": [-1240, 380],
            "webhookId": "visual-creatives",
            "notes": ("Запуск агента по ссылке: POST http://192.168.56.10:5678/webhook/visual-creatives. "
                      "В теле можно передать {\"brief_path\": \"...\", \"overrides\": {...}}."),
        },

        # --- ШАГ 1. ВХОДНОЙ БРИФ --------------------------------------------
        code_node("Входной бриф", 3, js["input"], [-1020, 290],
                  "Определяет, откуда читать бриф: файл по умолчанию или путь из webhook."),
        read_file_node("Читать бриф", 4, "={{ $json.brief_path }}", [-820, 290],
                       "Входной бриф — внешний JSON-файл, а не константа внутри схемы."),
        text_node("Текст брифа", 5, [-620, 290],
                  "readWriteFile отдаёт файл бинарником, поэтому текст достаём отдельным узлом."),
        code_node("Разобрать бриф", 6, js["parse"], [-420, 290],
                  "Проверка обязательных разделов брифа и сборка списка вариантов."),

        # --- ШАГ 2. АГЕНТ-ПРОМТ-ИНЖЕНЕР --------------------------------------
        {
            "parameters": {
                "promptType": "define",
                "text": "={{ $json.brief_pack }}",
                "options": {"systemMessage": "=" + system_prompt},
            },
            "id": nid(7),
            "name": "Агент: промт-инженер",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "typeVersion": 3.1,
            "position": [-200, 290],
            "notes": "LLM-агент: превращает бриф в промты для генератора изображений.",
        },
        {
            # format=json — встроенная опция узла «Output Format». Без неё
            # модель-рассуждалка отвечает прозой («Let me craft prompts…») и до
            # JSON просто не доходит: узел «Собрать промты» каждый раз уходил на
            # запасные промты из брифа. С включённым JSON модель отдаёт готовый
            # объект с четырьмя вариантами за ~14 секунд (проверено на боевом
            # входе агента: tools/agent-model-probe).
            "parameters": {"model": MODEL, "options": {"temperature": 0.4, "format": "json"}},
            "id": nid(8),
            "name": "Ollama Chat Model",
            "type": "@n8n/n8n-nodes-langchain.lmChatOllama",
            "typeVersion": 1,
            "position": [-260, 520],
            "credentials": {"ollamaApi": OLLAMA_CRED},
            "notes": "Модель агента-промт-инженера. Включён Output Format = JSON.",
        },

        # --- ШАГ 3. ПРОМТЫ И ВАРИАТИВНОСТЬ -----------------------------------
        code_node("Собрать промты", 9, js["prompts"], [20, 290],
                  "Разбор ответа агента, предохранители и замена одного фрагмента для альтернативы."),

        # --- ШАГ 4. ГЕНЕРАЦИЯ ------------------------------------------------
        code_node("Генерация FLUX", 10, js["generate"], [240, 290],
                  "Быстрые спейсы Hugging Face, а если квота исчерпана — запасной Stable Horde."),
        has_url_node("Есть ссылка на картинку?", 27, [400, 290],
                     "Разные генераторы отдают результат по-разному: ссылкой или base64."),
        download_node("Скачать изображение", 11, [560, 180],
                      "Скачивание картинки в binary: ответ записывается как файл, а не как текст."),
        code_node("Картинка из base64", 29, js["img_from_b64"], [560, 400],
                  "Запасной генератор отдаёт base64 — собираем из него настоящий файл."),
        write_file_node("Сохранить изображение", 12, DATA_DIR + "/images/{{ $json.file_name }}", [740, 290],
                        "Креативы складываются в папку images на диске сервера."),

        # --- ШАГ 5. АВТОПРОВЕРКА КРЕАТИВА ------------------------------------
        code_node("Собрать запрос к Vision", 13, js["vision_req"], [900, 290],
                  "Промт проверки + картинка в base64 из binary-поля."),
        vision_node("Vision: проверка", 14, [1120, 290],
                    "Vision-модель оценивает креатив по чек-листу заказчика."),
        code_node("Оценка по чек-листу", 15, js["checklist_1"], [1340, 290],
                  "Четыре пункта чек-листа из шаблона + решение, нужна ли правка."),

        # --- ШАГ 6. ПРАВКА ТОЛЬКО ТЕХ, ГДЕ «НЕТ» БОЛЬШЕ ДВУХ -------------------
        {
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose",
                                "version": 2},
                    "conditions": [
                        {
                            "id": "need-fix-1",
                            "leftValue": "={{ $json.needs_fix }}",
                            "rightValue": "",
                            "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                        }
                    ],
                    "combinator": "and",
                },
                "looseTypeValidation": True,
                "options": {},
            },
            "id": nid(16),
            "name": "Нужна правка?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2.2,
            "position": [1560, 290],
            "notes": "Ветвление: больше двух «нет» — правим, иначе креатив идёт в таблицу как есть.",
        },
        code_node("Правка промта", 17, js["fix"], [1780, 120],
                  "Дописывает в промт уточнения по проваленным пунктам и берёт новый сид."),
        code_node("Генерация FLUX (правка)", 18, js["generate"], [1960, 120],
                  "Повторная генерация исправленного варианта."),
        has_url_node("Есть ссылка на картинку? (правка)", 28, [2120, 120]),
        download_node("Скачать изображение (правка)", 19, [2280, 10]),
        code_node("Картинка из base64 (правка)", 30, js["img_from_b64"], [2280, 230]),
        write_file_node("Сохранить изображение (правка)", 20,
                        DATA_DIR + "/images/{{ $json.file_name }}", [2460, 120]),
        code_node("Собрать запрос к Vision (правка)", 21, js["vision_req"], [2640, 120]),
        vision_node("Vision: проверка (правка)", 22, [2820, 120]),
        code_node("Оценка после правки", 23, js["checklist_2"], [3000, 120],
                  "Повторная оценка: та же модель, тот же чек-лист."),

        # --- ШАГ 7. РЕГИСТР И ТАБЛИЦА ----------------------------------------
        code_node("Регистр креативов", 24, js["registry"], [2000, 430],
                  "Свод результатов, сравнение альтернативы с базовым вариантом, CSV и Markdown."),
        write_file_node("Сохранить регистр", 25, DATA_DIR + "/{{ $json.file_name }}", [2220, 430],
                        "Три файла: registry.json, registry.csv, registry.md."),
        code_node("Итог", 26, js["final"], [2440, 430],
                  "Короткая сводка: её отдаёт webhook и видно в интерфейсе n8n."),
    ]

    # Раскладка на канве держится отдельно от описания узлов: так схема
    # читается слева направо, а ветки не наезжают друг на друга.
    LAYOUT = {
        "Запуск вручную (кнопка)": [-1240, 200],
        "Запуск по ссылке (Webhook)": [-1240, 460],
        "Входной бриф": [-1000, 300],
        "Читать бриф": [-800, 300],
        "Текст брифа": [-600, 300],
        "Разобрать бриф": [-400, 300],
        "Агент: промт-инженер": [-180, 300],
        "Ollama Chat Model": [-260, 580],
        "Собрать промты": [40, 300],
        "Генерация FLUX": [260, 300],
        "Есть ссылка на картинку?": [460, 300],
        "Скачать изображение": [680, 40],
        "Картинка из base64": [680, 560],
        "Сохранить изображение": [900, 300],
        "Собрать запрос к Vision": [1120, 300],
        "Vision: проверка": [1340, 300],
        "Оценка по чек-листу": [1560, 300],
        "Нужна правка?": [1780, 300],

        "Правка промта": [1980, 40],
        "Генерация FLUX (правка)": [2180, 40],
        "Есть ссылка на картинку? (правка)": [2380, 40],
        "Скачать изображение (правка)": [2600, -220],
        "Картинка из base64 (правка)": [2600, 300],
        "Сохранить изображение (правка)": [2820, 40],
        "Собрать запрос к Vision (правка)": [3040, 40],
        "Vision: проверка (правка)": [3260, 40],
        "Оценка после правки": [3480, 40],

        "Регистр креативов": [3700, 700],
        "Сохранить регистр": [3940, 700],
        "Итог": [4180, 700],
    }

    for node in nodes:
        if node["name"] in LAYOUT:
            node["position"] = LAYOUT[node["name"]]

    connections = {
        "Запуск вручную (кнопка)": {"main": [[{"node": "Входной бриф", "type": "main", "index": 0}]]},
        "Запуск по ссылке (Webhook)": {"main": [[{"node": "Входной бриф", "type": "main", "index": 0}]]},
        "Входной бриф": {"main": [[{"node": "Читать бриф", "type": "main", "index": 0}]]},
        "Читать бриф": {"main": [[{"node": "Текст брифа", "type": "main", "index": 0}]]},
        "Текст брифа": {"main": [[{"node": "Разобрать бриф", "type": "main", "index": 0}]]},
        "Разобрать бриф": {"main": [[{"node": "Агент: промт-инженер", "type": "main", "index": 0}]]},
        "Агент: промт-инженер": {"main": [[{"node": "Собрать промты", "type": "main", "index": 0}]]},
        "Собрать промты": {"main": [[{"node": "Генерация FLUX", "type": "main", "index": 0}]]},
        "Генерация FLUX": {"main": [[{"node": "Есть ссылка на картинку?", "type": "main", "index": 0}]]},
        "Есть ссылка на картинку?": {"main": [
            [{"node": "Скачать изображение", "type": "main", "index": 0}],
            [{"node": "Картинка из base64", "type": "main", "index": 0}],
        ]},
        "Скачать изображение": {"main": [[{"node": "Сохранить изображение", "type": "main", "index": 0}]]},
        "Картинка из base64": {"main": [[{"node": "Сохранить изображение", "type": "main", "index": 0}]]},
        "Сохранить изображение": {"main": [[{"node": "Собрать запрос к Vision", "type": "main", "index": 0}]]},
        "Собрать запрос к Vision": {"main": [[{"node": "Vision: проверка", "type": "main", "index": 0}]]},
        "Vision: проверка": {"main": [[{"node": "Оценка по чек-листу", "type": "main", "index": 0}]]},
        "Оценка по чек-листу": {"main": [[{"node": "Нужна правка?", "type": "main", "index": 0}]]},
        "Нужна правка?": {"main": [
            [{"node": "Правка промта", "type": "main", "index": 0}],
            [{"node": "Регистр креативов", "type": "main", "index": 0}],
        ]},
        "Правка промта": {"main": [[{"node": "Генерация FLUX (правка)", "type": "main", "index": 0}]]},
        "Генерация FLUX (правка)": {"main": [[{"node": "Есть ссылка на картинку? (правка)", "type": "main", "index": 0}]]},
        "Есть ссылка на картинку? (правка)": {"main": [
            [{"node": "Скачать изображение (правка)", "type": "main", "index": 0}],
            [{"node": "Картинка из base64 (правка)", "type": "main", "index": 0}],
        ]},
        "Скачать изображение (правка)": {"main": [[{"node": "Сохранить изображение (правка)", "type": "main", "index": 0}]]},
        "Картинка из base64 (правка)": {"main": [[{"node": "Сохранить изображение (правка)", "type": "main", "index": 0}]]},
        "Сохранить изображение (правка)": {"main": [[{"node": "Собрать запрос к Vision (правка)", "type": "main", "index": 0}]]},
        "Собрать запрос к Vision (правка)": {"main": [[{"node": "Vision: проверка (правка)", "type": "main", "index": 0}]]},
        "Vision: проверка (правка)": {"main": [[{"node": "Оценка после правки", "type": "main", "index": 0}]]},
        "Оценка после правки": {"main": [[{"node": "Регистр креативов", "type": "main", "index": 0}]]},
        "Регистр креативов": {"main": [[{"node": "Сохранить регистр", "type": "main", "index": 0}]]},
        "Сохранить регистр": {"main": [[{"node": "Итог", "type": "main", "index": 0}]]},
        "Ollama Chat Model": {"ai_languageModel": [[{"node": "Агент: промт-инженер",
                                                     "type": "ai_languageModel", "index": 0}]]},
    }

    wf = {
        "name": "Агент визуальных креативов: онлайн-школа английского языка",
        "nodes": nodes,
        "connections": connections,
        # saveExecutionProgress: n8n пишет состояние после каждого узла. Без него
        # у «долгих» прогонов (генерация ждёт очередь чужого сервиса) в интерфейсе
        # и в API не видно, на каком узле выполнение стоит, — только пустой runData.
        "settings": {"executionOrder": "v1", "saveExecutionProgress": True},
        "staticData": None,
        "pinData": {},
        "active": False,
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(wf, f, ensure_ascii=False, indent=2)

    print("Записано:", OUT)
    print("Узлов:", len(nodes))


if __name__ == "__main__":
    main()
