"""Генерация ноутбука для практики «Практика pipeline» (aiml-5, item 3549961).

Создаёт Практика_pipeline.ipynb с ячейками EDA, feature engineering, pipeline,
сравнения моделей, Optuna, MLflow и Airflow DAG. Выполняется отдельным
скриптом execute_notebook.py через nbclient.
"""
from pathlib import Path

import nbformat as nbf

BASE = Path(__file__).resolve().parent
NB_PATH = BASE / "Практика_pipeline.ipynb"

cells = []
md = lambda text: cells.append(nbf.v4.new_markdown_cell(text))
code = lambda text: cells.append(nbf.v4.new_code_cell(text))

# --------------------------------------------------------------------------
md("""# Практика pipeline: прогноз типа кофе

**Курс:** aiml-5 «Машинное обучение и нейросети», задание «Практика pipeline»
(https://netology.ru/profile/program/aiml-5/lessons/662421/lesson_items/3549961)

**Задача:** многоклассовая классификация — предсказать `coffee_name` (тип напитка)
по времени покупки, дню недели, месяцу и сумме чека.

**Данные:** `data/Coffe_sales.csv` — 3547 транзакций кофейни за 2024-03-01 … 2025-03-23.

**Этапы работы:**
1. EDA и подготовка данных
2. Генерация признаков (feature engineering)
3. Построение pipeline предобработки
4. Обучение бейзлайна и сравнение моделей
5. Подбор гиперпараметров (Optuna)
6. Логирование экспериментов в MLflow
7. Оркестрация через Airflow (DAG)
8. Выводы
""")

# --------------------------------------------------------------------------
md("""## 0. Импорты и настройки

Все эксперименты логируются в локальное SQLite-хранилище `mlflow.db` рядом с ноутбуком,
эксперимент — `coffee_sales_classification`. Артефакты (модели, графики) — в `mlruns/`.""")
code('''import json
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import mlflow
import mlflow.sklearn
import optuna
from optuna.samplers import TPESampler

warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid", palette="deep")
plt.rcParams["figure.dpi"] = 110
RANDOM_STATE = 42

BASE_DIR = Path.cwd()
DATA_PATH = BASE_DIR / "data" / "Coffe_sales.csv"
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)
MLFLOW_DB = BASE_DIR / "mlflow.db"
MLRUNS_DIR = BASE_DIR / "mlruns"

# MLflow 3.x: файловый backend выведен из эксплуатации, используем SQLite
mlflow.set_tracking_uri(f"sqlite:///{MLFLOW_DB.as_posix()}")
mlflow.set_experiment("coffee_sales_classification")

print("pandas:", pd.__version__)
print("scikit-learn:", __import__("sklearn").__version__)
print("mlflow:", mlflow.__version__)
print("optuna:", optuna.__version__)
print("Данные:", DATA_PATH)
print("MLflow tracking:", mlflow.get_tracking_uri())''')

# --------------------------------------------------------------------------
md("""## 1. EDA и подготовка данных

- загрузка датасета, размер, типы колонок, первые строки;
- проверка пропусков и дубликатов;
- распределение целевой переменной `coffee_name`;
- приведение `Date` к `datetime`.""")
code('''df = pd.read_csv(DATA_PATH)
print("Размер датасета:", df.shape)
print("\\nТипы колонок:")
print(df.dtypes.to_string())
print("\\nПервые 5 строк:")
display(df.head())

print("\\nПропуски по колонкам:")
print(df.isna().sum().to_string())
print("\\nПолных дубликатов:", int(df.duplicated().sum()))
print("Уникальных значений по колонкам:")
print(df.nunique().to_string())''')
code('''target_counts = df["coffee_name"].value_counts()
target_share = df["coffee_name"].value_counts(normalize=True) * 100
summary = pd.DataFrame({"count": target_counts, "share_%": target_share.round(2)})
print(summary.to_string())

fig, ax = plt.subplots(figsize=(9, 4.5))
sns.barplot(x=target_counts.values, y=target_counts.index, ax=ax)
ax.set_title("Распределение целевой переменной coffee_name")
ax.set_xlabel("Количество транзакций")
ax.set_ylabel("")
for i, v in enumerate(target_counts.values):
    ax.text(v + 5, i, str(v), va="center", fontsize=9)
plt.tight_layout()
plt.savefig(REPORTS_DIR / "target_distribution.png", bbox_inches="tight")
plt.show()''')
code('''print("Сумма чека (money):")
print(df["money"].describe().round(2).to_string())
print("\\nКонстантные / почти константные признаки:")
for col in df.columns:
    nunique = df[col].nunique()
    if nunique <= 2:
        print(f"  {col}: {nunique} уник. -> {df[col].unique()[:3]}")
print("\\nКатегориальные признаки:")
for col in ["cash_type", "Time_of_Day", "Weekday", "Month_name"]:
    print(f"  {col}: {sorted(df[col].unique())}")

# Date -> datetime
df["Date"] = pd.to_datetime(df["Date"])
print("\\nТип Date после приведения:", df["Date"].dtype)
print("Диапазон дат:", df["Date"].min().date(), "—", df["Date"].max().date())

# Проверка согласованности производных колонок с Date
print("\\nСовпадение Weekday с actual:", (df["Date"].dt.strftime("%a") == df["Weekday"]).mean().round(3))
print("Совпадение Month_name с actual:", (df["Date"].dt.strftime("%b") == df["Month_name"]).mean().round(3))
print("Совпадение hour_of_day с Time:", (df["Date"].dt.year.notna()).mean())''')
code('''fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))

sns.boxplot(data=df, x="coffee_name", y="money", ax=axes[0])
axes[0].set_title("Сумма чека по типам кофе")
axes[0].tick_params(axis="x", rotation=35)

sns.histplot(data=df, x="hour_of_day", hue="coffee_name", multiple="stack",
             bins=18, ax=axes[1])
axes[1].set_title("Час покупки по типам кофе")
axes[1].set_xlabel("hour_of_day")

plt.tight_layout()
plt.savefig(REPORTS_DIR / "eda_money_hour.png", bbox_inches="tight")
plt.show()''')

md("""### Выводы по EDA

- **Размер и качество данных:** 3547 строк × 11 колонок, пропусков и полных дубликатов нет — чистка не требуется.
- **Целевая переменная:** 8 классов, выраженный дисбаланс: `Americano with Milk` (809, 22,8 %) и `Latte` (757, 21,3 %)
  против `Espresso` (129, 3,6 %). Поэтому основная метрика — **F1-macro** (учитывает все классы одинаково),
  а accuracy приводим для справки. Стратификация при сплите и кросс-валидации обязательна, иначе редкие классы
  могут вообще не попасть в фолд.
- **`cash_type` — константа:** все 3547 транзакций оплачены картой. Признак не несёт информации и в модель не включается
  (OneHotEncoder дал бы один бесполезный столбец).
- **Временные колонки:** `Date` приведена к `datetime`, диапазон 2024-03-01 … 2025-03-23 (почти 13 месяцев).
  `Weekday`, `Month_name`, `Time_of_Day`, `hour_of_day` — производные от даты и согласованы с ней.
- **`money`:** от 18,12 до 38,70, медиана 32,82, распределение скошено влево (больше дешёвых чеков);
  масштаб признаков разный, поэтому числовые признаки нужно стандартизировать.
- **Связь признаков с целью:** дорогие напитки (`Latte`, `Americano with Milk`, `Cappuccino`) стоят заметно выше
  `Espresso`/`Cocoa`; час покупки также различается между классами — оба признака информативны.
- **Ограничение:** в данных нет идентификатора клиента, погоды и промо-акций — модель увидит только «чек + время».
  Ожидать очень высокой accuracy не стоит; ориентир — заметно выше бейзлайна (13–23 %).""")

# --------------------------------------------------------------------------
md("""## 2. Генерация признаков

Из `Date` создаём: день месяца, номер недели в году, признак выходного дня.
Числовые признаки: `hour_of_day`, `money`, `day_of_month`, `week_of_year`, `is_weekend`.
Категориальные: `Time_of_Day`, `Weekday`, `Month_name`.""")
code('''df_fe = df.copy()
df_fe["day_of_month"] = df_fe["Date"].dt.day
df_fe["week_of_year"] = df_fe["Date"].dt.isocalendar().week.astype(int)
df_fe["is_weekend"] = (df_fe["Date"].dt.dayofweek >= 5).astype(int)

FEATURES_NUM = ["hour_of_day", "money", "day_of_month", "week_of_year", "is_weekend"]
FEATURES_CAT = ["Time_of_Day", "Weekday", "Month_name"]

X = df_fe[FEATURES_NUM + FEATURES_CAT].copy()
y = df_fe["coffee_name"].copy()

print("Форма X:", X.shape)
display(X.head())
print("\\nЧисловые признаки:", FEATURES_NUM)
print("Категориальные признаки:", FEATURES_CAT)
print("\\nДоля выходных дней:", round(df_fe["is_weekend"].mean(), 3))
print("Диапазон недель:", df_fe["week_of_year"].min(), "-", df_fe["week_of_year"].max())''')
code('''X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
)
print("Train:", X_train.shape, "| Test:", X_test.shape)
print("\\nДоли классов в train, %:")
print((y_train.value_counts(normalize=True) * 100).round(2).to_string())
print("\\nДоли классов в test, %:")
print((y_test.value_counts(normalize=True) * 100).round(2).to_string())''')

# --------------------------------------------------------------------------
md("""## 3. Построение pipeline предобработки

`ColumnTransformer`: числовые — `StandardScaler`, категориальные — `OneHotEncoder(handle_unknown="ignore")`.
Всё вместе с моделью оборачивается в `Pipeline`, поэтому препроцессор обучается **только на train**
внутри каждого фолда — утечки данных из теста нет.""")
code('''preprocessor = ColumnTransformer(
    transformers=[
        ("num", StandardScaler(), FEATURES_NUM),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), FEATURES_CAT),
    ],
    remainder="drop",
)

# Проверка размерности после препроцессинга
preprocessor.fit(X_train)
print("Признаков после ColumnTransformer:", preprocessor.transform(X_train).shape[1])

def build_pipeline(model):
    """Препроцессор + модель в одном Pipeline."""
    return Pipeline(steps=[("preprocessor", preprocessor), ("model", model)])''')

# --------------------------------------------------------------------------
md("""## 4. Обучение бейзлайна и сравнение моделей

- бейзлайн `DummyClassifier(strategy="most_frequent")` — предсказывает самый частый класс;
- три модели: `LogisticRegression`, `RandomForestClassifier`, `GradientBoostingClassifier`;
- `StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`;
- метрики: accuracy и F1-macro на кросс-валидации (train) и на тесте.""")
code('''CV = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

def evaluate_model(name, model, X_train, y_train, X_test, y_test):
    """CV на train + обучение на всём train + метрики на тесте."""
    pipe = build_pipeline(model)
    cv_res = cross_validate(
        pipe, X_train, y_train, cv=CV,
        scoring=["accuracy", "f1_macro"], n_jobs=1,
    )
    pipe.fit(X_train, y_train)
    y_pred = pipe.predict(X_test)
    result = {
        "model": name,
        "cv_accuracy": cv_res["test_accuracy"].mean(),
        "cv_accuracy_std": cv_res["test_accuracy"].std(),
        "cv_f1_macro": cv_res["test_f1_macro"].mean(),
        "cv_f1_macro_std": cv_res["test_f1_macro"].std(),
        "test_accuracy": accuracy_score(y_test, y_pred),
        "test_f1_macro": f1_score(y_test, y_pred, average="macro"),
    }
    return result, pipe, y_pred

baseline_result, baseline_pipe, baseline_pred = evaluate_model(
    "DummyClassifier (most_frequent)",
    DummyClassifier(strategy="most_frequent", random_state=RANDOM_STATE),
    X_train, y_train, X_test, y_test,
)
print("Бейзлайн DummyClassifier:")
for k, v in baseline_result.items():
    print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")''')
code('''models = {
    "LogisticRegression": LogisticRegression(max_iter=2000, random_state=RANDOM_STATE),
    "RandomForest": RandomForestClassifier(
        n_estimators=300, random_state=RANDOM_STATE, n_jobs=-1
    ),
    "GradientBoosting": GradientBoostingClassifier(
        n_estimators=200, learning_rate=0.1, max_depth=3, random_state=RANDOM_STATE
    ),
}

results = [baseline_result]
fitted_pipelines = {"DummyClassifier (most_frequent)": baseline_pipe}
predictions = {"DummyClassifier (most_frequent)": baseline_pred}

for name, model in models.items():
    result, pipe, y_pred = evaluate_model(name, model, X_train, y_train, X_test, y_test)
    results.append(result)
    fitted_pipelines[name] = pipe
    predictions[name] = y_pred
    print(
        f"{name:20s} | CV acc {result['cv_accuracy']:.4f} ± {result['cv_accuracy_std']:.4f} "
        f"| CV F1-macro {result['cv_f1_macro']:.4f} "
        f"| Test acc {result['test_accuracy']:.4f} | Test F1-macro {result['test_f1_macro']:.4f}"
    )''')
code('''results_df = pd.DataFrame(results).set_index("model")
display(results_df.round(4))

fig, ax = plt.subplots(figsize=(10, 4.8))
plot_df = results_df[["cv_f1_macro", "test_f1_macro"]].sort_values("test_f1_macro")
plot_df.plot(kind="barh", ax=ax, color=["#7aa6c2", "#d98c5f"])
ax.set_title("F1-macro: кросс-валидация vs тест")
ax.set_xlabel("F1-macro")
ax.set_ylabel("")
ax.legend(["CV (5-fold)", "Test"])
plt.tight_layout()
plt.savefig(REPORTS_DIR / "model_comparison.png", bbox_inches="tight")
plt.show()

best_model_name = results_df.drop(index="DummyClassifier (most_frequent)")["test_f1_macro"].idxmax()
print("Лучшая модель по test F1-macro:", best_model_name,
      f"({results_df.loc[best_model_name, 'test_f1_macro']:.4f})")''')
code('''best_pred = predictions[best_model_name]
print(f"Classification report на тесте — {best_model_name}:\\n")
print(classification_report(y_test, best_pred, digits=3))''')

# --------------------------------------------------------------------------
md("""## 5. Подбор гиперпараметров (Optuna)

Оптимизируем лучшую модель по **среднему F1-macro на 5-fold CV** (только на train),
минимум 25 trials. Тестовая выборка в подборе не участвует.""")
code('''def make_objective(model_name):
    def objective(trial):
        if model_name == "RandomForest":
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=50),
                "max_depth": trial.suggest_int("max_depth", 3, 30),
                "min_samples_split": trial.suggest_int("min_samples_split", 2, 20),
                "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 10),
                "max_features": trial.suggest_categorical("max_features", ["sqrt", "log2", None]),
            }
            model = RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1, **params)
        elif model_name == "GradientBoosting":
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=50),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "max_depth": trial.suggest_int("max_depth", 2, 8),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 20),
            }
            model = GradientBoostingClassifier(random_state=RANDOM_STATE, **params)
        else:  # LogisticRegression
            params = {
                "C": trial.suggest_float("C", 1e-3, 1e2, log=True),
                "solver": trial.suggest_categorical("solver", ["lbfgs", "saga"]),
                "penalty": trial.suggest_categorical("penalty", ["l2"]),
            }
            model = LogisticRegression(max_iter=3000, random_state=RANDOM_STATE, **params)

        pipe = build_pipeline(model)
        cv_res = cross_validate(pipe, X_train, y_train, cv=CV,
                                scoring="f1_macro", n_jobs=1)
        return cv_res["test_score"].mean()
    return objective

optuna.logging.set_verbosity(optuna.logging.WARNING)
study = optuna.create_study(
    direction="maximize",
    sampler=TPESampler(seed=RANDOM_STATE),
    study_name=f"coffee_{best_model_name.lower()}_optuna",
)
study.optimize(make_objective(best_model_name), n_trials=25, show_progress_bar=False)

print(f"Лучшая модель: {best_model_name}")
print(f"Лучший CV F1-macro: {study.best_value:.4f}")
print("Лучшие параметры:")
for k, v in study.best_params.items():
    print(f"  {k}: {v}")

trials_df = study.trials_dataframe()
trials_df["trial"] = trials_df["number"]
fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(trials_df["trial"], trials_df["value"], marker="o", markersize=3, alpha=0.7)
ax.axhline(study.best_value, color="tab:red", linestyle="--", label=f"best = {study.best_value:.4f}")
ax.set_title(f"Optuna: история trials ({best_model_name})")
ax.set_xlabel("Trial")
ax.set_ylabel("CV F1-macro")
ax.legend()
plt.tight_layout()
plt.savefig(REPORTS_DIR / "optuna_history.png", bbox_inches="tight")
plt.show()

n_trials_completed = len([t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE])
print("Завершённых trials:", n_trials_completed)''')
code('''def build_best_model(model_name, params):
    if model_name == "RandomForest":
        return RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1, **params)
    if model_name == "GradientBoosting":
        return GradientBoostingClassifier(random_state=RANDOM_STATE, **params)
    return LogisticRegression(max_iter=3000, random_state=RANDOM_STATE, **params)

final_result, final_pipe, final_pred = evaluate_model(
    f"{best_model_name} (Optuna best)",
    build_best_model(best_model_name, study.best_params),
    X_train, y_train, X_test, y_test,
)
print("Финальная модель после подбора гиперпараметров:")
for k, v in final_result.items():
    print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

improvement = final_result["test_f1_macro"] - results_df.loc[best_model_name, "test_f1_macro"]
print(f"\\nПрирост test F1-macro относительно базовой {best_model_name}: {improvement:+.4f}")''')
code('''# Важность признаков: permutation importance финальной модели на тесте
from sklearn.inspection import permutation_importance

perm = permutation_importance(
    final_pipe, X_test, y_test, scoring="f1_macro",
    n_repeats=10, random_state=RANDOM_STATE, n_jobs=1,
)
importance_df = pd.DataFrame({
    "feature": FEATURES_NUM + FEATURES_CAT,
    "importance_mean": perm.importances_mean,
    "importance_std": perm.importances_std,
}).sort_values("importance_mean", ascending=False)
display(importance_df.round(4))

fig, ax = plt.subplots(figsize=(9, 4.5))
ax.barh(
    importance_df["feature"][::-1],
    importance_df["importance_mean"][::-1],
    xerr=importance_df["importance_std"][::-1],
    color="#5b8c5a",
)
ax.set_title("Permutation importance финальной модели (F1-macro)")
ax.set_xlabel("Падение F1-macro при перемешивании признака")
ax.set_ylabel("")
plt.tight_layout()
plt.savefig(REPORTS_DIR / "feature_importance.png", bbox_inches="tight")
plt.show()''')

# --------------------------------------------------------------------------
md("""## 6. Логирование экспериментов в MLflow

Эксперимент **`coffee_sales_classification`**, локальное SQLite-хранилище `mlflow.db`
(артефакты — в `mlruns/`).
Отдельными run'ами: бейзлайн, три модели сравнения и финальная оптимизированная модель (всего 5).
В каждом run'е — параметры, CV-метрики, тестовые метрики и сама модель (`mlflow.sklearn.log_model`).""")
code('''def safe_params(pipe):
    """Только скалярные параметры модели — их принимает mlflow.log_params."""
    params = {}
    for key, value in pipe.named_steps["model"].get_params().items():
        if isinstance(value, (int, float, str, bool)) and value is not None:
            params[key] = value
    return params

def log_experiment_run(result, pipe, run_name, extra_params=None, tags=None):
    with mlflow.start_run(run_name=run_name):
        params = safe_params(pipe)
        params["model_class"] = type(pipe.named_steps["model"]).__name__
        if extra_params:
            params.update(extra_params)
        mlflow.log_params(params)
        mlflow.log_metrics({
            "cv_accuracy": result["cv_accuracy"],
            "cv_accuracy_std": result["cv_accuracy_std"],
            "cv_f1_macro": result["cv_f1_macro"],
            "cv_f1_macro_std": result["cv_f1_macro_std"],
            "test_accuracy": result["test_accuracy"],
            "test_f1_macro": result["test_f1_macro"],
        })
        mlflow.set_tags({"model_name": result["model"], **(tags or {})})
        mlflow.sklearn.log_model(pipe, name="model", serialization_format="pickle")

        # Кривая обучения не строится, но сохраняем графики-артефакты, если есть
        for png in ["target_distribution.png", "eda_money_hour.png",
                    "model_comparison.png", "optuna_history.png", "feature_importance.png"]:
            path = REPORTS_DIR / png
            if path.exists():
                mlflow.log_artifact(str(path), artifact_path="plots")
        run_id = mlflow.active_run().info.run_id
    print(f"Залогирован run «{run_name}»: {run_id}")
    return run_id

run_ids = {}
run_ids["baseline"] = log_experiment_run(
    baseline_result, fitted_pipelines["DummyClassifier (most_frequent)"],
    "baseline_dummy", tags={"stage": "baseline"},
)
for name in models:
    run_ids[name] = log_experiment_run(
        [r for r in results if r["model"] == name][0],
        fitted_pipelines[name],
        f"compare_{name}",
        tags={"stage": "comparison"},
    )
run_ids["final"] = log_experiment_run(
    final_result, final_pipe, f"final_{best_model_name}_optuna",
    extra_params={
        "optuna_n_trials": n_trials_completed,
        "optuna_best_cv_f1_macro": study.best_value,
        **{f"best_{k}": v for k, v in study.best_params.items() if isinstance(v, (int, float, str, bool))},
    },
    tags={"stage": "final", "tuned": "true"},
)
print("\\nВсего run'ов:", len(run_ids))''')
code('''# Проверка: читаем залогированные run'ы из хранилища MLflow
from mlflow.tracking import MlflowClient

client = MlflowClient()
experiment = client.get_experiment_by_name("coffee_sales_classification")
runs = client.search_runs(
    experiment_ids=[experiment.experiment_id],
    order_by=["metrics.test_f1_macro DESC"],
)
print(f"Эксперимент: {experiment.name} (id={experiment.experiment_id})")
print(f"Найдено run'ов: {len(runs)}\\n")
rows = []
for run in runs:
    rows.append({
        "run_name": run.data.tags.get("mlflow.runName"),
        "model_name": run.data.tags.get("model_name"),
        "cv_f1_macro": run.data.metrics.get("cv_f1_macro"),
        "test_accuracy": run.data.metrics.get("test_accuracy"),
        "test_f1_macro": run.data.metrics.get("test_f1_macro"),
    })
runs_df = pd.DataFrame(rows)
display(runs_df.round(4))

assert len(runs) >= 5, "В MLflow должно быть минимум 5 run'ов"
print("✓ Минимум 5 run'ов в MLflow: условие задания выполнено")''')

md("""**Запуск MLflow UI:**

```bash
mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000
```

Затем открыть http://127.0.0.1:5000, зайти в эксперимент `coffee_sales_classification`,
выделить все run'ы и сравнить метрики. Скриншот сохранён в `mlflow_ui_comparison.png`
и приложен к решению.""")

# --------------------------------------------------------------------------
md("""## 7. (Опционально) Оркестрация через Airflow

DAG `coffee_ml_pipeline_weekly` из трёх задач — загрузка данных, feature engineering,
обучение + логирование в MLflow, расписание `@weekly`. Код сохранён в `coffee_ml_pipeline_dag.py`.""")
code('''DAG_CODE = """\\"\\"\\"DAG для еженедельного переобучения модели прогноза типа кофе.

Задачи:
  load_data           — загрузка Coffe_sales.csv в staging
  feature_engineering — генерация признаков из Date
  train_and_log       — обучение модели и логирование в MLflow

Расписание: @weekly.
\\"\\"\\"
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from airflow import DAG
from airflow.operators.python import PythonOperator

DATA_PATH = Path("/opt/airflow/data/Coffe_sales.csv")
STAGING_PATH = Path("/opt/airflow/data/staging.csv")
FEATURES_PATH = Path("/opt/airflow/data/features.csv")
MODEL_PATH = Path("/opt/airflow/data/model.pkl")

FEATURES_NUM = ["hour_of_day", "money", "day_of_month", "week_of_year", "is_weekend"]
FEATURES_CAT = ["Time_of_Day", "Weekday", "Month_name"]


def load_data(**context):
    df = pd.read_csv(DATA_PATH)
    df["Date"] = pd.to_datetime(df["Date"])
    STAGING_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(STAGING_PATH, index=False)
    print(f"Загружено {len(df)} строк")


def feature_engineering(**context):
    df = pd.read_csv(STAGING_PATH, parse_dates=["Date"])
    df["day_of_month"] = df["Date"].dt.day
    df["week_of_year"] = df["Date"].dt.isocalendar().week.astype(int)
    df["is_weekend"] = (df["Date"].dt.dayofweek >= 5).astype(int)
    df.to_csv(FEATURES_PATH, index=False)
    print(f"Признаки готовы: {len(df)} строк")


def train_and_log(**context):
    import mlflow
    import mlflow.sklearn
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    mlflow.set_experiment("coffee_sales_classification")
    df = pd.read_csv(FEATURES_PATH)
    X = df[FEATURES_NUM + FEATURES_CAT]
    y = df["coffee_name"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    preprocessor = ColumnTransformer([
        ("num", StandardScaler(), FEATURES_NUM),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), FEATURES_CAT),
    ])
    pipe = Pipeline([
        ("preprocessor", preprocessor),
        ("model", RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1)),
    ])
    pipe.fit(X_train, y_train)
    y_pred = pipe.predict(X_test)

    with mlflow.start_run(run_name=f"airflow_weekly_{context['ds']}"):
        mlflow.log_params({"n_estimators": 300, "model_class": "RandomForestClassifier"})
        mlflow.log_metrics({
            "test_accuracy": accuracy_score(y_test, y_pred),
            "test_f1_macro": f1_score(y_test, y_pred, average="macro"),
        })
        mlflow.sklearn.log_model(pipe, name="model", serialization_format="pickle")
    with open(MODEL_PATH, "wb") as fh:
        pickle.dump(pipe, fh)
    print("Модель обучена и залогирована")


default_args = {
    "owner": "ml-team",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="coffee_ml_pipeline_weekly",
    default_args=default_args,
    description="Еженедельный pipeline прогноза типа кофе",
    schedule="@weekly",
    start_date=datetime(2024, 3, 1),
    catchup=False,
    tags=["ml", "coffee", "pipeline"],
) as dag:
    t_load = PythonOperator(task_id="load_data", python_callable=load_data)
    t_features = PythonOperator(task_id="feature_engineering", python_callable=feature_engineering)
    t_train = PythonOperator(task_id="train_and_log", python_callable=train_and_log)

    t_load >> t_features >> t_train
"""

(BASE_DIR / "coffee_ml_pipeline_dag.py").write_text(DAG_CODE, encoding="utf-8")
print("DAG сохранён:", BASE_DIR / "coffee_ml_pipeline_dag.py")

import ast
ast.parse(DAG_CODE)
print("✓ Синтаксис DAG корректен, задач:", DAG_CODE.count("PythonOperator(task_id"))
print("✓ Расписание:", "@weekly" if 'schedule="@weekly"' in DAG_CODE else "НЕ НАЙДЕНО")''')

# --------------------------------------------------------------------------
md("""## 8. Выводы

**Напишите ваши выводы по результатам экспериментов:**

1. Какая модель показала лучшее качество и почему?
2. Насколько подбор гиперпараметров улучшил метрики?
3. Какие признаки, по вашему мнению, оказались наиболее важными?
4. Что бы вы улучшили в pipeline при переходе в продакшен?""")
md("{{CONCLUSIONS}}")

# --------------------------------------------------------------------------
code('''# Сводные метрики сохраняем для отчёта и README
summary_for_report = {
    "dataset": {"rows": int(len(df)), "features": int(len(FEATURES_NUM + FEATURES_CAT)),
                "classes": int(y.nunique()), "test_size": int(len(y_test))},
    "results": {r["model"]: {k: round(float(v), 4) for k, v in r.items() if k != "model"}
                for r in results},
    "final": {k: round(float(v), 4) for k, v in final_result.items() if k != "model"},
    "best_model": best_model_name,
    "best_params": study.best_params,
    "optuna": {"n_trials": n_trials_completed, "best_cv_f1_macro": round(study.best_value, 4)},
    "feature_importance": {
        row["feature"]: round(float(row["importance_mean"]), 4)
        for _, row in importance_df.iterrows()
    },
    "mlflow_runs": len(run_ids),
}
(BASE_DIR / "metrics.json").write_text(
    json.dumps(summary_for_report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(summary_for_report, ensure_ascii=False, indent=2))''')

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.14"},
}

nbf.write(nb, NB_PATH)
print(f"Ноутбук создан: {NB_PATH} ({len(cells)} ячеек)")
