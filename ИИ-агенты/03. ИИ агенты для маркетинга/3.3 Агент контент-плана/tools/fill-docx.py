#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Заполняет шаблон ДЗ «Практика: агент контент-плана» результатами работы агента.

Данные берутся из ответа агента (result/agent-response.json), который возвращает
workflow n8n: там есть контент-план, чек-лист и уже собранный по структуре шаблона
документ в markdown. Из markdown вытаскиваются разделы 1–5, чек-лист берётся
из JSON — так в docx попадает ровно то, что сгенерировал агент, без ручной правки.

Запуск:
    python tools/fill-docx.py
"""
import copy
import io
import json
import os
import re
import sys

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(HERE, "source", "Шаблон_к_ДЗ_Агент_контент-плана.docx")
RESPONSE = os.path.join(HERE, "result", "agent-response.json")
OUT = os.path.join(HERE, "result", "Шаблон_к_ДЗ_Агент_контент-плана_заполненный.docx")

AGENT_URL = "http://192.168.56.10:5678/workflow/aVbrHDT74iC2tRQ1"
WEBHOOK_URL = "http://192.168.56.10:5678/webhook/content-plan"


# --- разбор markdown-документа агента ---------------------------------------
def section(md, title):
    """Текст раздела от заголовка '### <title>' до следующего заголовка."""
    m = re.search(r"^#{2,3} " + re.escape(title) + r"\s*\n([\s\S]*?)(?=\n#{2,3} |\Z)", md, re.M)
    return m.group(1).strip() if m else ""


def bold_value(text, label):
    """Значение после '**<label>:**' до конца строки. Пробелы не пропускаем через
    перевод строки, иначе в значение попадёт первый пункт следующего списка."""
    m = re.search(r"\*\*" + re.escape(label) + r":\*\*[ \t]*([^\n]*)", text)
    return m.group(1).strip() if m else ""


def bullets(text):
    """Пункты списка из markdown-блока."""
    out = []
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("- "):
            out.append(s[2:].strip().rstrip("."))
    return out


def plain(text):
    """Абзац без markdown-разметки, списков и подзаголовков."""
    lines = []
    for line in text.split("\n"):
        s = line.strip()
        if not s or s.startswith("- ") or s.startswith("**") or s.startswith("|") or s.endswith(":"):
            continue
        lines.append(s)
    return " ".join(lines).strip()


# --- запись в ячейки ---------------------------------------------------------
def set_cell(cell, lines):
    """Заменяет содержимое ячейки: первый абзац остаётся, остальные добавляются."""
    if isinstance(lines, str):
        lines = [lines]
    lines = [str(x) for x in lines if str(x).strip()]
    if not lines:
        lines = [""]

    cell.text = lines[0]
    for extra in lines[1:]:
        cell.add_paragraph(extra)


def set_par(p, text):
    """Заменяет текст абзаца, сохраняя оформление первого прогона."""
    runs = p.runs
    if runs:
        runs[0].text = text
        for r in runs[1:]:
            r.text = ""
    else:
        p.add_run(text)


def main():
    data = json.load(io.open(RESPONSE, encoding="utf-8"))
    md = data["document_md"]
    plan = data["plan"]
    checklist = data["checklist"]

    doc = docx.Document(TEMPLATE)
    tables = doc.tables
    paras = doc.paragraphs

    # --- раздел 1 -----------------------------------------------------------
    product = plain(section(md, "1.1. Бренд и продукт"))
    goal = section(md, "1.2. Цель бизнеса")
    audience = section(md, "1.3. Целевая аудитория")
    pains_block = section(md, "1.4. Боли и потребности")
    position = section(md, "1.5. Позиционирование и тон коммуникации")

    pains_part = pains_block.split("**Ключевые потребности аудитории:**")[0]
    needs_part = pains_block.split("**Ключевые потребности аудитории:**")[-1]

    set_cell(tables[0].rows[0].cells[0], product)
    set_cell(tables[1].rows[0].cells[0], bold_value(goal, "Основная цель"))
    set_cell(tables[2].rows[0].cells[0], bullets(goal))
    set_cell(tables[3].rows[0].cells[0], bold_value(audience, "Основная аудитория"))
    set_cell(tables[4].rows[0].cells[0], bullets(pains_part))
    set_cell(tables[5].rows[0].cells[0], bullets(needs_part))
    set_cell(tables[6].rows[0].cells[0], bold_value(position, "Позиционирование"))

    # --- раздел 2 -----------------------------------------------------------
    agent = section(md, "2.2. Роль и цель агента")
    set_cell(tables[7].rows[0].cells[0], [
        "Агент собран в n8n (self-hosted) вместе с локальной моделью через Ollama, "
        "поэтому вместо ссылки на Yandex AI Studio — ссылки на рабочий агент:",
        "",
        "Запуск агента: " + WEBHOOK_URL,
        "Редактор workflow: " + AGENT_URL,
    ])
    set_cell(tables[8].rows[0].cells[0], bold_value(agent, "Роль"))
    set_cell(tables[9].rows[0].cells[0], bold_value(agent, "Цель агента"))

    inputs = [
        "brand-brief.md — бриф бренда: продукт, цель бизнеса, ЦА, боли и потребности, "
        "позиционирование, тон коммуникации.",
        "content-rules.md — правила контента: периодичность, баланс задач недели, список "
        "рубрик, разрешённые форматы, требования площадок, запрещённые формулировки, "
        "лестница статусов публикации.",
        "content-log.csv — журнал прошлых публикаций: 18 записей с площадкой, рубрикой, "
        "задачей, форматом и метриками (просмотры, реакции, комментарии, сохранения, ER).",
        "Календарь недели — даты с ближайшего понедельника, чтобы план лёг на реальные дни.",
    ]
    set_cell(tables[10].rows[0].cells[0], inputs)
    set_cell(tables[11].rows[0].cells[0],
             plain(section(md, "2.4. Формат результата агента")))

    # --- раздел 3 -----------------------------------------------------------
    set_cell(tables[12].rows[0].cells[0],
             data["plan_period"] + " (" + str(data["publications"]) + " публикаций, "
             "по одной в день; каждая выходит в двух версиях — Telegram и ВКонтакте)")

    plan_table = tables[13]
    for i, item in enumerate(plan):
        row = plan_table.rows[i + 1]
        values = [
            "%d. %s (%s)" % (item["day"], item["date"], item["weekday"]),
            item["rubric"],
            item["topic"],
            item["format"],
            "Telegram + ВКонтакте",
            item["goal"],
        ]
        for cell, val in zip(row.cells, values):
            set_cell(cell, val)

    # --- раздел 4 -----------------------------------------------------------
    posts = section(md, "4.1. Публикация 1 (пост)")
    post2 = section(md, "4.2. Публикация 2 (пост)")
    reels = section(md, "4.3. Сценарий короткого видео (рилс)")

    def meta(block, label):
        m = re.search(r"\*\*" + re.escape(label) + r":\*\*\s*(.+)", block)
        return m.group(1).strip() if m else ""

    def text_of(block, label):
        # двоеточие у модели может стоять и до закрывающих «**», и после —
        # учитываем оба варианта
        m = re.search(r"\*\*" + re.escape(label) + r":?\*\*[^\n]*\n\n([\s\S]*?)(?=\n\n\*\*|\Z)", block)
        return m.group(1).strip() if m else ""

    set_par(paras[49], "Рубрика: " + meta(posts, "Рубрика"))
    set_par(paras[50], "Тема: " + meta(posts, "Тема"))
    set_cell(tables[14].rows[0].cells[0], [
        "Версия для Telegram (" + re.search(r"\*\*Версия для Telegram\*\* \(([^)]+)\)", posts).group(1) + "):",
        "",
        text_of(posts, "Версия для Telegram"),
        "",
        "Версия для ВКонтакте (" + re.search(r"\*\*Версия для ВКонтакте\*\* \(([^)]+)\)", posts).group(1) + "):",
        "",
        text_of(posts, "Версия для ВКонтакте"),
    ])

    set_par(paras[54], "Рубрика: " + meta(post2, "Рубрика"))
    set_par(paras[55], "Тема: " + meta(post2, "Тема"))
    set_cell(tables[15].rows[0].cells[0], [
        "Версия для Telegram (" + re.search(r"\*\*Версия для Telegram\*\* \(([^)]+)\)", post2).group(1) + "):",
        "",
        text_of(post2, "Версия для Telegram"),
        "",
        "Версия для ВКонтакте (" + re.search(r"\*\*Версия для ВКонтакте\*\* \(([^)]+)\)", post2).group(1) + "):",
        "",
        text_of(post2, "Версия для ВКонтакте"),
    ])

    set_par(paras[59], "Рубрика: " + meta(reels, "Рубрика"))
    set_par(paras[60], "Тема видео: " + meta(reels, "Тема видео"))
    set_par(paras[61], "Формат сценария (по сценам или шагам): по сценам, с визуальным рядом "
                       "и текстом на экране.")
    set_par(paras[62], "Хук (первые 3–5 секунд): " + text_of(reels, "Хук (первые 3–5 секунд)"))
    set_par(paras[63], "Основная часть: " + text_of(reels, "Основная часть"))
    set_par(paras[64], "Финальная мысль / вывод: " + text_of(reels, "Финальная мысль / вывод"))

    # --- раздел 5 -----------------------------------------------------------
    demo = section(md, "5. Сценарий публикации в демо-среде")
    order_block = demo.split("**Порядок выхода материалов:**")[-1].split("### 5.2.")[0]
    set_cell(tables[16].rows[0].cells[0], bold_value(demo, "Периодичность публикаций"))
    set_cell(tables[17].rows[0].cells[0], [
        re.sub(r"^\d+\.\s*", "- ", line.strip())
        for line in order_block.split("\n") if re.match(r"^\d+\.\s", line.strip())
    ])

    # таблица точек контроля в шаблоне не нарисована — вставляем её сами.
    # В том же разделе ниже идёт таблица расписания демо-среды, её пропускаем:
    # у неё первая колонка начинается с «Дата».
    checkpoints = []
    for line in section(md, "5.2. Точки проверки качества").split("\n"):
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells[0] == "На каком этапе идёт проверка":
            continue
        if cells[0] == "Дата":
            break
        checkpoints.append(cells)

    anchor = paras[73]._p
    new_table = doc.add_table(rows=1, cols=3)
    new_table.style = tables[13].style
    anchor.addnext(new_table._tbl)

    header = new_table.rows[0].cells
    for cell, title in zip(header, ["На каком этапе идёт проверка", "Что именно проверяется",
                                    "В каких случаях сценарий нужно остановить"]):
        set_cell(cell, title)
    for cp in checkpoints:
        row = new_table.add_row().cells
        for cell, val in zip(row, cp):
            set_cell(cell, val)

    # --- раздел 6: чек-лист ------------------------------------------------
    check_table = tables[18]
    marks = {"да": 2, "частично": 3, "нет": 4}
    for item in checklist:
        row = check_table.rows[item["n"]]
        set_cell(row.cells[0], str(item["n"]))
        set_cell(row.cells[1], item["question"])
        answer = item["answer"].strip().lower()
        for name, idx in marks.items():
            set_cell(row.cells[idx], "V" if answer == name else "")
        set_cell(row.cells[5], item["comment"])

    doc.save(OUT)
    print("Записано:", OUT)
    print("Таблиц в документе:", len(doc.tables), "| строк чек-листа:", len(checklist),
          "| точек контроля:", len(checkpoints))


if __name__ == "__main__":
    main()
