# Практика pipeline (aiml-5, item 3549961)

Домашнее задание курса **aiml-5 «Машинное обучение и нейросети»** — построение
воспроизводимого ML-pipeline для многоклассовой классификации типа кофе.

- Задание: https://netology.ru/profile/program/aiml-5/lessons/662421/lesson_items/3549961
- Текст задания и исходные файлы: `../../task/Задание.md`, `../../task/Coffe_sales/`, `../../task/coffee_ml_pipeline/`
- На проверку **не отправлялось** (по указанию пользователя).

## Что сделано

| Шаг задания | Где в ноутбуке |
|---|---|
| EDA и выводы | раздел 1 |
| Feature engineering из `Date` | раздел 2 |
| `ColumnTransformer` + `Pipeline` | раздел 3 |
| Бейзлайн и 3 модели, 5-fold CV | раздел 4 |
| Optuna, 25 trials | раздел 5 |
| 5 run'ов в MLflow + скриншот UI | раздел 6, `mlflow_ui_comparison.png` |
| Airflow DAG `@weekly` | раздел 7, `coffee_ml_pipeline_dag.py` |
| Выводы | раздел 8 |

## Файлы

| Файл | Назначение |
|---|---|
| `Практика_pipeline.ipynb` | выполненный ноутбук со всеми шагами и выводами |
| `build_notebook.py` | генератор ноутбука (ячейки описаны в коде) |
| `execute_notebook.py` | прогон ноутбука через `nbclient` |
| `finalize_notebook.py` | подстановка фактических выводов из `metrics.json` |
| `coffee_ml_pipeline_dag.py` | DAG Apache Airflow (3 задачи, `@weekly`) |
| `mlflow_ui_comparison.png` | скриншот MLflow UI со сравнением run'ов |
| `metrics.json` | сводные метрики всех моделей |
| `data/Coffe_sales.csv` | данные (3547 строк) |
| `reference_coffee_ml_pipeline.ipynb` | опорный ноутбук-шаблон из задания |
| `mlflow.db` + `mlruns/` | хранилище MLflow (SQLite + артефакты) |
| `reports/*.png` | графики EDA, сравнения моделей, Optuna, важности признаков |

## Результаты

<!-- METRICS_START -->
Данные: 3547 транзакций, 8 классов, train 2837 / test 710. Метрика отбора — F1-macro.

| Модель | CV accuracy | CV F1-macro | Test accuracy | Test F1-macro |
|---|---|---|---|---|
| DummyClassifier (most_frequent) | 0,2281 | 0,0464 | 0,2282 | 0,0464 |
| LogisticRegression | 0,6239 | 0,5193 | 0,6268 | 0,5381 |
| RandomForest | 0,6376 | 0,5733 | 0,6437 | 0,5784 |
| GradientBoosting | 0,6422 | 0,5848 | 0,6634 | 0,6151 |
| **GradientBoosting + Optuna (финал)** | **0,6585** | **0,6160** | **0,6676** | **0,6241** |

- Лучшая модель — **GradientBoosting**; Optuna (25 trials) подобрала
  `n_estimators=300`, `learning_rate≈0,012`, `max_depth=8`, `subsample≈0,946`, `min_samples_leaf=4`
  и дала **+0,0090** F1-macro на тесте относительно дефолтной версии.
- Важность признаков (permutation importance, F1-macro): `money` 0,467, `week_of_year` 0,197,
  `hour_of_day` 0,060, `day_of_month` 0,037, `Weekday` 0,026, `Month_name` 0,026,
  `is_weekend` 0,003, `Time_of_Day` 0,003.
- В MLflow залогировано 5 run'ов (baseline + 3 модели + финальная), скриншот — `mlflow_ui_comparison.png`.
<!-- METRICS_END -->

## Как воспроизвести

```bash
pip install pandas scikit-learn mlflow optuna matplotlib seaborn nbclient nbformat
python build_notebook.py
python execute_notebook.py
python finalize_notebook.py

# UI со сравнением экспериментов
mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000
```

## Особенности окружения

- Python 3.14, pandas 3.0, scikit-learn 1.9, mlflow 3.17, optuna 5.0.
- В MLflow 3.x файловый backend переведён в maintenance mode, поэтому используется
  SQLite (`sqlite:///mlflow.db`), артефакты — в `mlruns/`.
- В pandas 3.0 строковые колонки имеют dtype `str`, поэтому признаки заданы явными
  списками (`FEATURES_NUM`, `FEATURES_CAT`), а не через `select_dtypes("object")`.
- `cash_type` — константа (`card` во всех 3547 строках), в модель не включён.
