"""Подстановка фактических выводов и ссылки на скриншот MLflow в готовый ноутбук."""
import json
from pathlib import Path

import nbformat

BASE = Path(__file__).resolve().parent
NB_PATH = BASE / "Практика_pipeline.ipynb"

metrics = json.loads((BASE / "metrics.json").read_text(encoding="utf-8"))
res = metrics["results"]
best = metrics["best_model"]
fin = metrics["final"]
base_res = res["DummyClassifier (most_frequent)"]
best_res = res[best]
gain_optuna = fin["test_f1_macro"] - best_res["test_f1_macro"]
gain_vs_base = fin["test_f1_macro"] - base_res["test_f1_macro"]

model_rows = "\n".join(
    f"| {name} | {v['cv_accuracy']:.4f} | {v['cv_f1_macro']:.4f} | "
    f"{v['test_accuracy']:.4f} | {v['test_f1_macro']:.4f} |"
    for name, v in res.items()
)

best_params_text = ", ".join(f"`{k}={v}`" for k, v in metrics["best_params"].items())

imp = metrics.get("feature_importance", {})
imp_top = sorted(imp.items(), key=lambda kv: kv[1], reverse=True)[:4]
imp_text = ", ".join(f"`{k}` ({v:+.4f})" for k, v in imp_top)

if best == "RandomForest":
    why = (
        "Случайный лес устойчив к разному масштабу признаков, хорошо ловит нелинейные "
        "взаимодействия «чек × время» и не требует сложной настройки."
    )
elif best == "GradientBoosting":
    why = (
        "Градиентный бустинг последовательно исправляет ошибки предыдущих деревьев и точнее "
        "ловит нелинейные зависимости между суммой чека, часом покупки и типом напитка."
    )
else:
    why = (
        "Логистическая регрессия оказалась достаточной для этого набора признаков: зависимость "
        "типа напитка от чека и времени близка к линейной в one-hot пространстве."
    )

conclusions = f"""### Итоги экспериментов

| Модель | CV accuracy | CV F1-macro | Test accuracy | Test F1-macro |
|---|---|---|---|---|
{model_rows}

**1. Лучшая модель и почему.** Лучший результат по тесту показала **{best}**
(test accuracy = {best_res['test_accuracy']:.4f}, F1-macro = {best_res['test_f1_macro']:.4f}).
{why}. Бейзлайн `DummyClassifier` даёт F1-macro всего {base_res['test_f1_macro']:.4f},
поэтому выигрыш моделей ({gain_vs_base:+.4f}) — это реальный сигнал, а не следствие дисбаланса классов.

**2. Эффект подбора гиперпараметров.** Optuna ({metrics['optuna']['n_trials']} trials) подобрала
{best_params_text}. Лучший CV F1-macro = {metrics['optuna']['best_cv_f1_macro']:.4f};
на тесте финальная модель дала accuracy = {fin['test_accuracy']:.4f} и F1-macro = {fin['test_f1_macro']:.4f},
то есть **{gain_optuna:+.4f}** к F1-macro относительно версии с дефолтными параметрами.
Подбор дал умеренный прирост: основная часть качества определяется самими признаками,
а не тонкой настройкой — типичная картина для табличных данных с малым числом информативных колонок.

**3. Наиболее важные признаки.** По permutation importance финальной модели (падение F1-macro
при перемешивании признака на тесте) лидируют: {imp_text}.
Это согласуется с EDA: сумма чека и час покупки лучше всего разделяют дорогие молочные напитки
(Latte, Cappuccino, Americano with Milk) и дешёвые Espresso/Cocoa, а день недели, месяц и признаки
календаря добавляют слабый сезонный сигнал. `cash_type` исключён: все транзакции оплачены картой,
признак константный.

**4. Что улучшить при переходе в продакшен.**
- Добавить признаки, которых нет в данных: погода, промо-акции, состав заказа, история клиента —
  именно они обычно дают основной прирост для прогноза покупки.
- Хранить не только `mlflow.db` (SQLite) и артефакты, но и версионирование данных (DVC)
  и реестр моделей MLflow (`registered_model_name`, стадии Staging/Production).
- Валидировать по времени (`TimeSeriesSplit`), а не случайным сплитом: случайный сплит завышает
  метрики, так как соседние транзакции одного дня попадают и в train, и в test.
- Мониторить дрейф: распределение чеков и меню меняется, нужны алерты на падение F1-macro.
- Обернуть препроцессор и модель в один артефакт (уже сделано через `Pipeline`) и отдавать
  предсказания через REST/батч, а не переобучать на каждый запрос.
- Автоматизировать переобучение (Airflow DAG `@weekly`) и добавить тесты на схему входных данных.
"""

nb = nbformat.read(NB_PATH, as_version=4)
replaced = False
for cell in nb.cells:
    if cell.cell_type == "markdown" and ("{{CONCLUSIONS}}" in cell.source or "Итоги экспериментов" in cell.source):
        cell.source = conclusions
        replaced = True
    if cell.cell_type == "markdown" and "Запуск MLflow UI" in cell.source and "mlflow_ui_comparison.png" not in cell.source:
        cell.source += "\n\n![Сравнение экспериментов в MLflow UI](mlflow_ui_comparison.png)"

if not replaced:
    raise SystemExit("Не найдена ячейка с плейсхолдером {{CONCLUSIONS}}")

nbformat.write(nb, NB_PATH)
print("Выводы подставлены, скриншот добавлен в ноутбук")
