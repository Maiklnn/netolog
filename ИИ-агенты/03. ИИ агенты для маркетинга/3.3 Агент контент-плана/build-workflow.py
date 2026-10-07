#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сборщик workflow «Агент контент-плана» для n8n.

Читает JS-код узлов из tools/*.js и системные промпты из tools/02-strategist-prompt.md
и tools/04-copywriter-prompt.md, подставляет их в JSON workflow и записывает результат
в workflow-content-agent.json.

Запуск:  python build-workflow.py
"""
import json
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "tools")
OUT = os.path.join(HERE, "workflow-content-agent.json")

OLLAMA_CRED = {"id": "DEHgfM1I0ZJBmGoo", "name": "Ollama (10.0.2.2:11434)"}
MODEL = "deepseek-v4.1-flash:cloud"
DATA_DIR = "/var/lib/n8n/.n8n-files/content-agent"


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


def llm_node(name, node_id, prompt_field, system_prompt, position, notes, prefix="",
             prompt_expr=None):
    # Короткое напоминание о формате дописывается прямо в задание: рассуждающая
    # модель охотнее держит формат, если требование стоит и в последнем сообщении.
    # prompt_expr нужен там, где задание целиком готовит предыдущий узел —
    # так повторная попытка учитывается в одном месте, а не в выражении n8n.
    expr = prompt_expr or ("$json." + prompt_field)
    text = "={{ " + expr + " }}"
    if prefix:
        text = '={{ "' + prefix.replace('"', '\\"').replace("\n", "\\n") + '\\n\\n" + ' + expr + ' }}'
    return {
        "parameters": {
            "promptType": "define",
            "text": text,
            "options": {"systemMessage": "=" + system_prompt},
        },
        "id": node_id,
        "name": name,
        "type": "@n8n/n8n-nodes-langchain.agent",
        "typeVersion": 3.1,
        "position": position,
        "notes": notes,
    }


def ollama_node(name, node_id, position, temperature):
    return {
        "parameters": {"model": MODEL, "options": {"temperature": temperature}},
        "id": node_id,
        "name": name,
        "type": "@n8n/n8n-nodes-langchain.lmChatOllama",
        "typeVersion": 1,
        "position": position,
        "credentials": {"ollamaApi": OLLAMA_CRED},
    }


def write_file_node(name, node_id, file_name_expr, position, notes):
    return {
        "parameters": {
            "operation": "write",
            # "=" в начале делает значение выражением n8n: без него {{ … }}
            # попадёт в имя файла буквально
            "fileName": "=" + file_name_expr,
            "dataPropertyName": "data",
            "options": {},
        },
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.readWriteFile",
        "typeVersion": 1,
        "position": position,
        "notes": notes,
    }


def main():
    prepare_input = read("01-prepare-input.js")
    strategist_prompt = read("02-strategist-prompt.md").strip()
    parse_plan = read("03-parse-plan.js")
    copywriter_prompt = read("04-copywriter-prompt.md").strip()
    parse_content = read("05-parse-content.js")
    self_check = read("06-self-check.js")
    build_demo = read("07-build-demo.js")
    build_document = read("08-build-document.js")
    prepare_md = read("09-prepare-md.js")
    prepare_csv = read("10-prepare-csv.js")

    P = "c3000000-0000-4000-8000-0000000000"

    nodes = [
        # --- триггеры -------------------------------------------------------
        {
            "parameters": {
                "rule": {"interval": [{"field": "weeks", "weeksInterval": 1,
                                       "triggerAtDay": [4], "triggerAtHour": 10,
                                       "triggerAtMinute": 0}]}
            },
            "id": P + "01",
            "name": "Расписание (еженедельно, Чт 10:00)",
            "type": "n8n-nodes-base.scheduleTrigger",
            "typeVersion": 1.2,
            "position": [-1240, 260],
            "notes": "Регулярный запуск: каждый четверг в 10:00 по времени сервера. "
                     "К четвергу есть данные о публикациях недели, а до понедельника "
                     "остаётся время на согласование плана редактором.",
        },
        {
            "parameters": {},
            "id": P + "02",
            "name": "Запуск вручную (кнопка)",
            "type": "n8n-nodes-base.manualTrigger",
            "typeVersion": 1,
            "position": [-1240, 440],
            "notes": "Ручной запуск из интерфейса n8n кнопкой «Execute workflow».",
        },
        {
            "parameters": {
                "httpMethod": "GET",
                "path": "content-plan",
                "responseMode": "lastNode",
                "options": {},
            },
            "id": P + "03",
            "name": "Запуск по ссылке (Webhook)",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2,
            "position": [-1240, 620],
            "webhookId": "content-plan-agent",
            "notes": "Ручной запуск по ссылке: GET http://192.168.56.10:5678/webhook/content-plan",
        },

        # --- ШАГ 1. СБОР ДАННЫХ: три источника -------------------------------
        read_file_node("1. Бриф бренда (MD)", P + "04", DATA_DIR + "/brand-brief.md", [-1000, 260],
                       "ИСТОЧНИК 1: бриф бренда «Тихий лес» — продукт, цель, ЦА, боли, тон."),
        text_node("1. Бриф бренда (текст)", P + "05", [-800, 260]),

        read_file_node("2. Правила контента (MD)", P + "06", DATA_DIR + "/content-rules.md", [-600, 260],
                       "ИСТОЧНИК 2: правила, которые задал пользователь — периодичность, "
                       "баланс задач, рубрики, форматы, площадки, запреты."),
        text_node("2. Правила контента (текст)", P + "07", [-400, 260]),

        read_file_node("3. Журнал публикаций (CSV)", P + "08", DATA_DIR + "/content-log.csv", [-200, 260],
                       "ИСТОЧНИК 3 (поведенческий): 18 прошлых публикаций с метриками — "
                       "агент учится на том, что сработало."),
        text_node("3. Журнал публикаций (текст)", P + "09", [0, 260]),

        # --- ШАГ 2. ПОДГОТОВКА ВХОДНЫХ ДАННЫХ --------------------------------
        code_node("Подготовка входных данных", P + "10", prepare_input, [200, 260],
                  "Разбирает журнал, считает результативность рубрик и форматов, "
                  "вычисляет даты недели и темы, которые повторять нельзя."),

        # --- ШАГ 3. СТРАТЕГИЯ (LLM) -------------------------------------------
        llm_node("Контент-стратег (LLM)", P + "11", "strategist_pack", strategist_prompt, [440, 260],
                 "LLM-узел с системным промптом контент-стратега: строит план на 7 дней "
                 "и выбирает 3 темы для полной проработки. При браке получает задание "
                 "пересобрать план.",
                 prefix="Не рассуждай. Верни только JSON контент-плана, "
                        "обёрнутый в маркеры ###ПЛАН### и ###КОНЕЦ###.",
                 prompt_expr="$json.strategist_input"),
        ollama_node("Ollama Chat Model (стратег)", P + "12", [420, 460], 0.2),

        # --- ШАГ 4. РАЗБОР ПЛАНА ----------------------------------------------
        code_node("Разбор контент-плана", P + "13", parse_plan, [660, 260],
                  "Достаёт JSON из ответа модели и проверяет план на соблюдение правил заказчика."),
        {
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "",
                                "typeValidation": "loose", "version": 2},
                    "conditions": [{
                        "id": "plan-retry-condition",
                        "leftValue": "={{ $json.need_retry }}",
                        "rightValue": "",
                        "operator": {"type": "boolean", "operation": "true",
                                     "singleValue": True},
                    }],
                    "combinator": "and",
                },
                "options": {},
            },
            "id": P + "26",
            "name": "План забракован?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2.2,
            "position": [780, 460],
            "notes": "Первая точка контроля качества: план проверяется на правила "
                     "заказчика до того, как по нему начнут писать тексты. "
                     "Забракованный план возвращается стратегу — не больше двух попыток.",
        },

        # --- ШАГ 5. ТЕКСТЫ (LLM) ----------------------------------------------
        llm_node("Копирайтер (LLM)", P + "14", "copywriter_task", copywriter_prompt, [900, 260],
                 "LLM-узел с системным промптом копирайтера: два поста в двух версиях "
                 "и сценарий рилса. При браке получает задание на переписывание.",
                 prefix="Не рассуждай и не пиши черновиков. Только готовые материалы "
                        "между маркерами, начиная с ###ПОСТ_1###. "
                        "Telegram — до 900 символов без хэштегов; ВКонтакте — до 1400 символов "
                        "и не больше 3 хэштегов. "
                        "Запрещённые слова: гарантия, гарантируем, срочно, лечит, вылечит, "
                        "депрессия, медицинский, уникальный, инновационный, только сегодня, "
                        "последний шанс, лучший на рынке, лучше конкурентов.",
                 prompt_expr="$json.copywriter_task_input"),
        ollama_node("Ollama Chat Model (копирайтер)", P + "15", [880, 460], 0.4),

        # --- ШАГ 6. РАЗБОР ТЕКСТОВ --------------------------------------------
        code_node("Разбор контента", P + "16", parse_content, [1120, 260],
                  "Разбирает материалы по маркерам, проверяет лимиты площадок "
                  "и запрещённые формулировки. При браке отправляет на переписывание."),
        {
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "",
                                "typeValidation": "loose", "version": 2},
                    "conditions": [{
                        "id": "retry-condition",
                        "leftValue": "={{ $json.need_retry }}",
                        "rightValue": "",
                        "operator": {"type": "boolean", "operation": "true",
                                     "singleValue": True},
                    }],
                    "combinator": "and",
                },
                "options": {},
            },
            "id": P + "25",
            "name": "Материалы забракованы?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2.2,
            "position": [1340, 260],
            "notes": "Точка контроля качества: если текст нарушил лимиты площадок "
                     "или запреты, он возвращается копирайтеру на переписывание. "
                     "Не больше двух попыток — дальше сценарий останавливается "
                     "и материалы уходят редактору как есть.",
        },
        code_node("Самопроверка качества", P + "17", self_check, [1560, 260],
                  "Сводит все проверки в чек-лист из шести вопросов шаблона ДЗ."),

        # --- ШАГ 7. ДЕМО-СРЕДА И ИТОГОВЫЙ ДОКУМЕНТ ---------------------------
        code_node("Сборка демо-публикации", P + "18", build_demo, [1780, 260],
                  "Готовит расписание для демо-среды: запись на каждую версию публикации, "
                  "статус не выше «на проверке»."),
        code_node("Сборка итогового документа", P + "19", build_document, [2000, 260],
                  "Собирает документ по структуре шаблона ДЗ: кейс → агент → план → "
                  "примеры → демо-среда → самооценка."),

        code_node("Подготовка файла (Markdown)", P + "20", prepare_md, [2220, 260],
                  "Переводит документ в бинарные данные: операция write ждёт файл, "
                  "а не текстовое поле."),
        write_file_node("Сохранить контент-план на диск", P + "21",
                        DATA_DIR + "/content-plan-{{ $json.run_date }}.md", [2420, 260],
                        "Документ сохраняется на диск сервера с датой начала недели в имени."),

        code_node("Подготовка файла (CSV)", P + "22", prepare_csv, [2620, 260],
                  "Готовит вторую запись — расписание для демо-среды."),
        write_file_node("Сохранить расписание демо-среды", P + "23",
                        DATA_DIR + "/demo-schedule-{{ $json.run_date }}.csv", [2820, 260],
                        "Расписание попадает в демо-среду: 14 строк (7 публикаций × 2 площадки)."),

        # --- ШАГ 8. ВЫДАЧА РЕЗУЛЬТАТА -----------------------------------------
        {
            "parameters": {
                "mode": "runOnceForAllItems",
                "jsCode": (
                    "// Финальный узел: возвращает результат работы агента.\n"
                    "// Он же служит ответом при запуске по ссылке (Webhook).\n"
                    "const doc = $('Сборка итогового документа').first().json;\n"
                    "const csv = $('Подготовка файла (CSV)').first().json;\n"
                    "return [{ json: {\n"
                    "  status: 'ok',\n"
                    "  plan_period: doc.plan_start + ' — ' + doc.plan_end,\n"
                    "  publications: doc.plan.length,\n"
                    "  demo_rows: csv.demo_rows,\n"
                    "  demo_on_check: csv.on_check,\n"
                    "  demo_draft: csv.draft,\n"
                    "  verdict: doc.verdict,\n"
                    "  checks_passed: doc.checks_passed,\n"
                    "  checks_total: doc.checks_total,\n"
                    "  files: {\n"
                    "    plan_md: 'content-plan-' + doc.plan_start + '.md',\n"
                    "    demo_csv: 'demo-schedule-' + doc.plan_start + '.csv'\n"
                    "  },\n"
                    "  checklist: doc.checklist,\n"
                    "  // номер последней попытки: видно, сработал ли повтор\n"
                    "  attempts: {\n"
                    "    plan: $('Разбор контент-плана').last().json.attempt,\n"
                    "    content: $('Разбор контента').last().json.attempt\n"
                    "  },\n"
                    "  failed_checks: doc.failed_checks,\n"
                    "  checks: doc.checks,\n"
                    "  plan: doc.plan,\n"
                    "  document_md: doc.document_md\n"
                    "} }];\n"
                ),
            },
            "id": P + "24",
            "name": "Показать результат",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [3020, 260],
            "notes": "Возвращает план, чек-лист и готовый документ: видно в интерфейсе n8n "
                     "и в ответе webhook.",
        },
    ]

    connections = {
        "Расписание (еженедельно, Чт 10:00)": {"main": [[{"node": "1. Бриф бренда (MD)", "type": "main", "index": 0}]]},
        "Запуск вручную (кнопка)": {"main": [[{"node": "1. Бриф бренда (MD)", "type": "main", "index": 0}]]},
        "Запуск по ссылке (Webhook)": {"main": [[{"node": "1. Бриф бренда (MD)", "type": "main", "index": 0}]]},
        "1. Бриф бренда (MD)": {"main": [[{"node": "1. Бриф бренда (текст)", "type": "main", "index": 0}]]},
        "1. Бриф бренда (текст)": {"main": [[{"node": "2. Правила контента (MD)", "type": "main", "index": 0}]]},
        "2. Правила контента (MD)": {"main": [[{"node": "2. Правила контента (текст)", "type": "main", "index": 0}]]},
        "2. Правила контента (текст)": {"main": [[{"node": "3. Журнал публикаций (CSV)", "type": "main", "index": 0}]]},
        "3. Журнал публикаций (CSV)": {"main": [[{"node": "3. Журнал публикаций (текст)", "type": "main", "index": 0}]]},
        "3. Журнал публикаций (текст)": {"main": [[{"node": "Подготовка входных данных", "type": "main", "index": 0}]]},
        "Подготовка входных данных": {"main": [[{"node": "Контент-стратег (LLM)", "type": "main", "index": 0}]]},
        "Контент-стратег (LLM)": {"main": [[{"node": "Разбор контент-плана", "type": "main", "index": 0}]]},
        "Разбор контент-плана": {"main": [[{"node": "План забракован?", "type": "main", "index": 0}]]},
        "План забракован?": {"main": [
            [{"node": "Контент-стратег (LLM)", "type": "main", "index": 0}],
            [{"node": "Копирайтер (LLM)", "type": "main", "index": 0}],
        ]},
        "Копирайтер (LLM)": {"main": [[{"node": "Разбор контента", "type": "main", "index": 0}]]},
        "Разбор контента": {"main": [[{"node": "Материалы забракованы?", "type": "main", "index": 0}]]},
        # ветка true (проверка не пройдена) возвращает задание копирайтеру:
        # это и есть повторная генерация; ветка false идёт дальше по сценарию
        "Материалы забракованы?": {"main": [
            [{"node": "Копирайтер (LLM)", "type": "main", "index": 0}],
            [{"node": "Самопроверка качества", "type": "main", "index": 0}],
        ]},
        "Самопроверка качества": {"main": [[{"node": "Сборка демо-публикации", "type": "main", "index": 0}]]},
        "Сборка демо-публикации": {"main": [[{"node": "Сборка итогового документа", "type": "main", "index": 0}]]},
        "Сборка итогового документа": {"main": [[{"node": "Подготовка файла (Markdown)", "type": "main", "index": 0}]]},
        "Подготовка файла (Markdown)": {"main": [[{"node": "Сохранить контент-план на диск", "type": "main", "index": 0}]]},
        "Сохранить контент-план на диск": {"main": [[{"node": "Подготовка файла (CSV)", "type": "main", "index": 0}]]},
        "Подготовка файла (CSV)": {"main": [[{"node": "Сохранить расписание демо-среды", "type": "main", "index": 0}]]},
        "Сохранить расписание демо-среды": {"main": [[{"node": "Показать результат", "type": "main", "index": 0}]]},
        "Ollama Chat Model (стратег)": {"ai_languageModel": [[{"node": "Контент-стратег (LLM)", "type": "ai_languageModel", "index": 0}]]},
        "Ollama Chat Model (копирайтер)": {"ai_languageModel": [[{"node": "Копирайтер (LLM)", "type": "ai_languageModel", "index": 0}]]},
    }

    wf = {
        "name": "Агент контент-плана: загородный клуб «Тихий лес»",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
        "staticData": None,
        "pinData": {},
        "active": False,
    }

    # Раскладка в три ряда: одной длинной линией схема не помещается на экран и
    # читается только в приближении, поэтому ряды компактнее по ширине.
    LAYOUT = {
        # ряд 1 — триггеры, источники данных, стратегия
        "Расписание (еженедельно, Чт 10:00)": [-1300, 80],
        "Запуск вручную (кнопка)": [-1300, 300],
        "Запуск по ссылке (Webhook)": [-1300, 520],
        "1. Бриф бренда (MD)": [-1060, 200],
        "1. Бриф бренда (текст)": [-860, 200],
        "2. Правила контента (MD)": [-660, 200],
        "2. Правила контента (текст)": [-460, 200],
        "3. Журнал публикаций (CSV)": [-260, 200],
        "3. Журнал публикаций (текст)": [-60, 200],
        "Подготовка входных данных": [160, 200],
        "Контент-стратег (LLM)": [400, 200],
        "Ollama Chat Model (стратег)": [380, 420],
        "Разбор контент-плана": [620, 200],
        "План забракован?": [840, 200],
        # ряд 2 — тексты и проверки качества
        "Копирайтер (LLM)": [100, 660],
        "Ollama Chat Model (копирайтер)": [80, 880],
        "Разбор контента": [340, 660],
        "Материалы забракованы?": [560, 660],
        "Самопроверка качества": [800, 660],
        "Сборка демо-публикации": [1020, 660],
        "Сборка итогового документа": [1240, 660],
        # ряд 3 — запись файлов и выдача результата
        "Подготовка файла (Markdown)": [100, 1120],
        "Сохранить контент-план на диск": [320, 1120],
        "Подготовка файла (CSV)": [540, 1120],
        "Сохранить расписание демо-среды": [760, 1120],
        "Показать результат": [980, 1120],
    }
    for n in nodes:
        if n["name"] in LAYOUT:
            n["position"] = LAYOUT[n["name"]]

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(wf, f, ensure_ascii=False, indent=2)

    print("Записано:", OUT)
    print("Узлов:", len(nodes))


if __name__ == "__main__":
    main()
