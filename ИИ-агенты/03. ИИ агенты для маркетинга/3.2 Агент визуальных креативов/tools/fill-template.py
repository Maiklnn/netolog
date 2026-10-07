#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Заполнение шаблона задания «Агент визуальных креативов».

Берёт исходный шаблон из source/Шаблон_для_выполнения_задания.xlsx и результат
работы агента (result/registry.json + папка creatives/), после чего пишет
готовый файл в result/.

Лист «Бриф»:
    B7 — текст брифа.

Лист «Генерация»: пять блоков по четыре строки (3–6, 7–10, 11–14, 15–18, 19–22).
Первый блок — вариант V1, второй — V2, третий — V3, четвёртый — альтернатива V4.
Заполняются столбцы A–G, ответы чек-листа идут в столбец I построчно
(в столбце H уже стоят формулировки пунктов из шаблона).

Запуск:  python tools/fill-template.py
"""
import io
import json
import os
import sys

import openpyxl
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(HERE, "source", "Шаблон_для_выполнения_задания.xlsx")
REGISTRY = os.path.join(HERE, "result", "registry.json")
CREATIVES = os.path.join(HERE, "creatives")
OUT = os.path.join(HERE, "result", "Шаблон_для_выполнения_задания_заполненный.xlsx")

BLOCKS = [(3, 6), (7, 10), (11, 14), (15, 18), (19, 22)]
THUMB = 118  # размер превью в пикселях


def brief_text(brief):
    """Собирает бриф в один читаемый текст для ячейки B7."""
    lines = []
    lines.append("Продукт: %s" % brief["product"]["name"])
    lines.append("Что это: %s" % brief["product"]["what"])
    lines.append("Цена: %s. Призыв: %s" % (brief["product"]["price"], brief["product"]["cta"]))
    lines.append("Бренд: %s — %s." % (brief["brand"]["name"], brief["brand"]["positioning"]))
    lines.append("Палитра: %s" % "; ".join(brief["brand"]["palette"].values()))
    lines.append("Тон: %s" % brief["brand"]["tone_of_voice"])
    lines.append("")
    for s in brief["segments"]:
        lines.append("ЦА %s: %s." % (s["id"], s["who"]))
        lines.append("    уровень: %s; инсайт: %s; задача: %s; сообщение: %s"
                     % (s["current_level"], s["insight"], s["job_to_be_done"], s["message"]))
    lines.append("")
    for p in brief["placements"]:
        lines.append("Площадка %s: %s, %s (%s). Зона под текст: %s. Требования: %s"
                     % (p["id"], p["name"], p["size"], p["ratio"], p["text_zone"], p["requirements"]))
    lines.append("")
    vl = brief["visual_language"]
    lines.append("Стиль: %s" % vl["style_base"])
    lines.append("Свет: %s. Композиция: %s. Съёмка: %s" % (vl["light"], vl["composition"], vl["photography"]))
    lines.append("")
    lines.append("Ограничения — на изображении НЕ должно быть:")
    for f in brief["restrictions"]["forbidden_elements"]:
        lines.append("    — %s" % f)
    lines.append("Технические ограничения:")
    for t in brief["restrictions"]["technical_restrictions"]:
        lines.append("    — %s" % t)
    lines.append("")
    lines.append("Вариативность: у альтернативы V4 меняется ровно один параметр — %s"
                 % brief["plan"][3]["changed_parameter"])
    lines.append("Без изменений: %s" % brief["plan"][3]["unchanged_parameters"])
    return "\n".join(lines)


def thumb(path):
    """Готовит уменьшенную копию картинки во временном файле.

    openpyxl умеет вставлять только файл или поток: уменьшённый «в памяти»
    объект PIL он при сохранении не находит. Поэтому сохраняем превью в temp.
    """
    import tempfile
    from PIL import Image as PILImage
    img = PILImage.open(path)
    w, h = img.size
    k = min(THUMB / float(w), THUMB / float(h))
    img = img.resize((max(1, int(w * k)), max(1, int(h * k))), PILImage.LANCZOS)
    fd, tmp = tempfile.mkstemp(suffix=".png", prefix="creative-")
    os.close(fd)
    img.convert("RGB").save(tmp, "PNG")
    return tmp


def main():
    with open(REGISTRY, encoding="utf-8") as f:
        reg = json.load(f)
    with open(os.path.join(HERE, "brief.json"), encoding="utf-8") as f:
        brief = json.load(f)

    rows = reg["rows"]
    by_id = {r["id"]: r for r in rows}
    order = [r["id"] for r in rows]

    # альтернатива (та, у которой заполнен «какой параметр изменён»)
    alt = None
    for r in rows:
        if r.get("changed_parameter"):
            alt = r
            break
    base = None
    if alt:
        for r in rows:
            if r.get("alternative_file") == alt["image_file"]:
                base = r
                break

    wb = openpyxl.load_workbook(TEMPLATE)

    # --- лист «Бриф» ---------------------------------------------------------
    ws = wb["Бриф"]
    ws["B7"] = brief_text(brief)
    ws["B7"].alignment = Alignment(wrap_text=True, vertical="top")

    # --- лист «Генерация» ----------------------------------------------------
    ws = wb["Генерация"]
    ws.column_dimensions["D"].width = 20
    ws.column_dimensions["E"].width = 20

    for idx, vid in enumerate(order):
        if idx >= len(BLOCKS):
            print("Внимание: строк в шаблоне меньше, чем вариантов — %s не поместился" % vid)
            continue
        top, bottom = BLOCKS[idx]
        r = by_id[vid]

        # у альтернативы в столбце «Площадка» помечаем, чья она пара: иначе
        # из таблицы не видно, зачем она вообще стоит отдельным блоком
        placed = r["placement"]
        if r.get("changed_parameter"):
            placed = "Альтернатива к V1 – " + placed
        ws.cell(row=top, column=1, value=placed)
        ws.cell(row=top, column=2, value=r["audience"])
        ws.cell(row=top, column=3, value=r["params"])
        ws.cell(row=top, column=4, value=r["image_file"] + "\n(папка creatives/)")

        alt_file = r.get("alternative_file") or ""
        if alt_file:
            ws.cell(row=top, column=5, value=alt_file + "\n(папка creatives/)")

        changed = r.get("changed_parameter") or ""
        if not changed and alt and base and r["id"] == base["id"]:
            changed = alt.get("changed_parameter") or ""
        if changed:
            ws.cell(row=top, column=6, value=changed)
        if r.get("difference"):
            ws.cell(row=top, column=7, value=r["difference"])

        for i, c in enumerate(r.get("checklist", [])):
            ws.cell(row=top + i, column=9, value=c["answer"])

        for row in range(top, bottom + 1):
            ws.row_dimensions[row].height = 30
            for col in (1, 2, 3, 4, 5, 6, 7):
                ws.cell(row=row, column=col).alignment = Alignment(
                    wrap_text=True, vertical="top", horizontal="left")
            ws.cell(row=row, column=9).alignment = Alignment(
                vertical="center", horizontal="center")

        for col, fname in ((4, r["image_file"]), (5, alt_file)):
            path = os.path.join(CREATIVES, fname) if fname else None
            if not path or not os.path.exists(path):
                continue
            image = XLImage(thumb(path))
            ws.add_image(image, "%s%d" % (openpyxl.utils.get_column_letter(col), top))

    if len(order) < len(BLOCKS):
        top, bottom = BLOCKS[len(order)]
        ws.cell(row=top, column=1, value="— (вариант не использовался)").font = Font(italic=True)

    wb.save(OUT)
    print("Записано:", OUT)
    print("Вариантов в шаблоне:", min(len(order), len(BLOCKS)))


if __name__ == "__main__":
    main()
