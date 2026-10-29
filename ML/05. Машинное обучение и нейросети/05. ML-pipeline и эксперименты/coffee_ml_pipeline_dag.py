"""DAG для еженедельного переобучения модели прогноза типа кофе.

Задачи:
  load_data           — загрузка Coffe_sales.csv в staging
  feature_engineering — генерация признаков из Date
  train_and_log       — обучение модели и логирование в MLflow

Расписание: @weekly.
"""
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
