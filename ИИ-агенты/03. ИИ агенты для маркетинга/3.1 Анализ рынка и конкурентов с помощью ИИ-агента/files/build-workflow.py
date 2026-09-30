#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сборщик workflow «Агент рыночной аналитики» для n8n.

Читает JS-код узлов из tools/*.js и системный промпт из tools/03-system-prompt.md,
подставляет их в JSON workflow и записывает результат в workflow-market-analyst.json.

Запуск:  python build-workflow.py
"""
import json
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "tools")
OUT = os.path.join(HERE, "workflow-market-analyst.json")

OLLAMA_CRED = {"id": "DEHgfM1I0ZJBmGoo", "name": "Ollama (10.0.2.2:11434)"}
MODEL = "deepseek-v4.1-flash:cloud"
DATA_DIR = "/var/lib/n8n/.n8n-files/market-analyst"


def read(name):
    with open(os.path.join(TOOLS, name), encoding="utf-8") as f:
        return f.read()


def code_node(name, node_id, js, position, notes=None):
    return {
        "parameters": {"mode": "runOnceForAllItems", "jsCode": js},
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
        "notes": notes or "",
    }


def read_file_node(name, node_id, path, position, notes=None):
    return {
        "parameters": {"operation": "read", "fileSelector": path, "options": {}},
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.readWriteFile",
        "typeVersion": 1,
        "position": position,
        "notes": notes or "",
    }


def text_node(name, node_id, position, notes=None):
    return {
        "parameters": {"operation": "text", "binaryPropertyName": "data",
                       "destinationKey": "data", "options": {}},
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.extractFromFile",
        "typeVersion": 1,
        "position": position,
        "notes": notes or "",
    }


def main():
    normalize = read("01-normalize.js")
    filter_group = read("02-filter-group.js")
    system_prompt = read("03-system-prompt.md").strip()
    clean_out = read("04-clean-output.js")
    self_check = read("05-self-check.js")
    prepare_file = read("06-prepare-file.js")

    nodes = [
        # --- триггеры -------------------------------------------------------
        {
            "parameters": {
                "rule": {"interval": [{"field": "weeks", "weeksInterval": 1,
                                       "triggerAtDay": [1], "triggerAtHour": 9,
                                       "triggerAtMinute": 0}]}
            },
            "id": "b1000000-0000-4000-8000-000000000001",
            "name": "Расписание (еженедельно, Пн 09:00)",
            "type": "n8n-nodes-base.scheduleTrigger",
            "typeVersion": 1.2,
            "position": [-1060, 260],
            "notes": "Регулярный запуск: каждый понедельник в 09:00 по времени сервера.",
        },
        {
            "parameters": {},
            "id": "b1000000-0000-4000-8000-000000000002",
            "name": "Запуск вручную (кнопка)",
            "type": "n8n-nodes-base.manualTrigger",
            "typeVersion": 1,
            "position": [-1060, 440],
            "notes": "Ручной запуск из интерфейса n8n кнопкой «Execute workflow».",
        },
        {
            "parameters": {
                "httpMethod": "GET",
                "path": "market-analyst",
                "responseMode": "lastNode",
                "options": {},
            },
            "id": "b1000000-0000-4000-8000-000000000016",
            "name": "Запуск по ссылке (Webhook)",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2,
            "position": [-1060, 620],
            "webhookId": "market-analyst-briefing",
            "notes": "Ручной запуск по ссылке: GET http://192.168.56.10:5678/webhook/market-analyst",
        },

        # --- ШАГ 1. СБОР ДАННЫХ: три источника -------------------------------
        read_file_node("1. Тарифы конкурентов (CSV)", "b1000000-0000-4000-8000-000000000003",
                       DATA_DIR + "/tariffs.csv", [-820, 260],
                       "ИСТОЧНИК 1 (первичный): таблица тарифов, собранная вручную с сайтов конкурентов."),
        text_node("1. Тарифы (текст)", "b1000000-0000-4000-8000-000000000004", [-620, 260]),

        read_file_node("2. Отзывы пользователей (CSV)", "b1000000-0000-4000-8000-000000000005",
                       DATA_DIR + "/reviews.csv", [-420, 260],
                       "ИСТОЧНИК 2 (поведенческий): отзывы с открытых площадок."),
        text_node("2. Отзывы (текст)", "b1000000-0000-4000-8000-000000000006", [-220, 260]),

        read_file_node("3. Обзор рынка (MD)", "b1000000-0000-4000-8000-000000000007",
                       DATA_DIR + "/market-review.md", [-20, 260],
                       "ИСТОЧНИК 3 (вторичный): дайджест отраслевых публикаций."),
        text_node("3. Обзор рынка (текст)", "b1000000-0000-4000-8000-000000000008", [180, 260]),

        # --- ШАГ 2. ПОДГОТОВКА ДАННЫХ ---------------------------------------
        code_node("Нормализация данных", "b1000000-0000-4000-8000-000000000009", normalize, [380, 260],
                  "Очистка, приведение к единому виду, объединение трёх источников в один контекст."),

        # --- ШАГ 3. ФИЛЬТРАЦИЯ, ГРУППИРОВКА, ВЫДЕЛЕНИЕ СИГНАЛОВ --------------
        code_node("Фильтрация и группировка", "b1000000-0000-4000-8000-000000000010", filter_group, [580, 260],
                  "Порог значимости, кросс-подтверждение, уровни: данные / наблюдение / инсайт / гипотеза."),

        # --- ШАГ 4. АНАЛИЗ (LLM) --------------------------------------------
        {
            "parameters": {
                "promptType": "define",
                "text": "={{ $json.analytics_pack }}",
                "options": {"systemMessage": "=" + system_prompt},
            },
            "id": "b1000000-0000-4000-8000-000000000011",
            "name": "Аналитик рынка (LLM)",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "typeVersion": 3.1,
            "position": [800, 260],
            "notes": "LLM-узел с системным промптом аналитика.",
        },
        {
            "parameters": {"model": MODEL, "options": {"temperature": 0.2}},
            "id": "b1000000-0000-4000-8000-000000000012",
            "name": "Ollama Chat Model",
            "type": "@n8n/n8n-nodes-langchain.lmChatOllama",
            "typeVersion": 1,
            "position": [760, 480],
            "credentials": {"ollamaApi": OLLAMA_CRED},
        },

        # --- ШАГ 5. ВЫХОДНОЙ РЕЗУЛЬТАТ --------------------------------------
        code_node("Очистка брифинга", "b1000000-0000-4000-8000-000000000013", clean_out, [1020, 260],
                  "Отсекает служебные рассуждения модели, собирает итоговый Markdown."),
        code_node("Самопроверка качества", "b1000000-0000-4000-8000-000000000014", self_check, [1240, 260],
                  "Автоматический чек-лист качества: разделы, основания, числа, шум."),
        code_node("Подготовка файла брифинга", "b1000000-0000-4000-8000-000000000018", prepare_file, [1440, 260],
                  "Переводит текст брифинга в бинарные данные: операция write ждёт файл, а не текстовое поле."),
        {
            "parameters": {
                "operation": "write",
                # "=" в начале делает значение выражением n8n: без него
                # {{ $json.run_date }} попадёт в имя файла буквально
                "fileName": "=" + DATA_DIR + "/briefing-{{ $json.run_date }}.md",
                "dataPropertyName": "data",
                "options": {},
            },
            "id": "b1000000-0000-4000-8000-000000000015",
            "name": "Сохранить брифинг в файл",
            "type": "n8n-nodes-base.readWriteFile",
            "typeVersion": 1,
            "position": [1640, 260],
            "notes": "Брифинг сохраняется на диск сервера с датой прогона в имени файла.",
        },
        {
            "parameters": {
                "mode": "runOnceForAllItems",
                "jsCode": (
                    "// Финальный узел: возвращает готовый брифинг и результат самопроверки.\n"
                    "// Он же служит ответом при запуске по ссылке (Webhook).\n"
                    "const b = $('Самопроверка качества').first().json;\n"
                    "return [{ json: {\n"
                    "  status: 'ok',\n"
                    "  generated_at: b.generated_at,\n"
                    "  run_date: b.run_date,\n"
                    "  counts: b.counts,\n"
                    "  self_check_passed: b.self_check_passed,\n"
                    "  self_check: b.self_check,\n"
                    "  briefing_md: b.briefing_md\n"
                    "} }];\n"
                ),
            },
            "id": "b1000000-0000-4000-8000-000000000017",
            "name": "Показать брифинг",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [1840, 260],
            "notes": "Возвращает брифинг: виден в интерфейсе n8n и в ответе webhook.",
        },
    ]

    connections = {
        "Расписание (еженедельно, Пн 09:00)": {"main": [[{"node": "1. Тарифы конкурентов (CSV)", "type": "main", "index": 0}]]},
        "Запуск вручную (кнопка)": {"main": [[{"node": "1. Тарифы конкурентов (CSV)", "type": "main", "index": 0}]]},
        "Запуск по ссылке (Webhook)": {"main": [[{"node": "1. Тарифы конкурентов (CSV)", "type": "main", "index": 0}]]},
        "1. Тарифы конкурентов (CSV)": {"main": [[{"node": "1. Тарифы (текст)", "type": "main", "index": 0}]]},
        "1. Тарифы (текст)": {"main": [[{"node": "2. Отзывы пользователей (CSV)", "type": "main", "index": 0}]]},
        "2. Отзывы пользователей (CSV)": {"main": [[{"node": "2. Отзывы (текст)", "type": "main", "index": 0}]]},
        "2. Отзывы (текст)": {"main": [[{"node": "3. Обзор рынка (MD)", "type": "main", "index": 0}]]},
        "3. Обзор рынка (MD)": {"main": [[{"node": "3. Обзор рынка (текст)", "type": "main", "index": 0}]]},
        "3. Обзор рынка (текст)": {"main": [[{"node": "Нормализация данных", "type": "main", "index": 0}]]},
        "Нормализация данных": {"main": [[{"node": "Фильтрация и группировка", "type": "main", "index": 0}]]},
        "Фильтрация и группировка": {"main": [[{"node": "Аналитик рынка (LLM)", "type": "main", "index": 0}]]},
        "Аналитик рынка (LLM)": {"main": [[{"node": "Очистка брифинга", "type": "main", "index": 0}]]},
        "Очистка брифинга": {"main": [[{"node": "Самопроверка качества", "type": "main", "index": 0}]]},
        "Самопроверка качества": {"main": [[{"node": "Подготовка файла брифинга", "type": "main", "index": 0}]]},
        "Подготовка файла брифинга": {"main": [[{"node": "Сохранить брифинг в файл", "type": "main", "index": 0}]]},
        "Сохранить брифинг в файл": {"main": [[{"node": "Показать брифинг", "type": "main", "index": 0}]]},
        "Ollama Chat Model": {"ai_languageModel": [[{"node": "Аналитик рынка (LLM)", "type": "ai_languageModel", "index": 0}]]},
    }

    wf = {
        "name": "Агент рыночной аналитики: онлайн-школы английского языка",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
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
