"""Собирает и исполняет ноутбук практики «Практика обучения модели».

Запуск из любой папки:
    python -I tools/build_notebook.py

Скрипт создаёт `Практика_обучения_модели.ipynb`, выполняет все ячейки
(Restart & Run All) и сохраняет ноутбук уже с выводами. Если хотя бы одна
ячейка завершится ошибкой, скрипт упадёт — это защита от сдачи «битого»
ноутбука.
"""

import os
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

BASE = Path(__file__).resolve().parent.parent
NOTEBOOK_PATH = BASE / "Практика_обучения_модели.ipynb"

cells = []


def md(text: str) -> None:
    cells.append(nbf.v4.new_markdown_cell(text.strip("\n")))


def code(text: str) -> None:
    cells.append(nbf.v4.new_code_cell(text.strip("\n")))


# --------------------------------------------------------------------------
md("""
# Практика обучения модели: прогноз оттока клиентов телеком-компании

**Курс:** «Специалист по искусственному интеллекту» (aiml-5)
**Занятие:** «Классический ML: обучение моделей в scikit-learn»
**Задание:** «Практика обучения модели» — полный цикл обучения модели в scikit-learn
**Дата выполнения:** 26 октября 2026 г.
**Среда:** Python 3.14, pandas 3.0.6, NumPy 2.5.2, scikit-learn 1.9.1, Jupyter Notebook
**Данные:** открытый набор Telco Customer Churn (IBM Sample Data Sets), 7 043 строки, 21 столбец
**Проверка:** ноутбук выполнен целиком через *Restart & Run All* — ошибок нет.

Ноутбук последовательно проходит все шаги задания: выбор и описание данных → предобработка
(пропуски, выбросы, кодирование категорий) → разделение на train/test → обучение
`LogisticRegression` методами `.fit()` и `.predict()` → расчёт метрик → проверка
вырожденности → вывод о пригодности модели. Перед каждой ячейкой с кодом есть пояснение.
""")

md("""
## 1. Постановка задачи и выбор данных

### 1.1. Бизнес-задача

Телеком-компании дешевле удержать клиента, чем привлечь нового. Поэтому важно заранее
находить абонентов, склонных к оттоку: с ними можно работать адресно — предложить скидку,
сменить тариф, подключить дополнительные услуги.

### 1.2. ML-задача

Бинарная классификация: по характеристикам клиента предсказать целевую переменную
**`Churn`** — уйдёт клиент (`Yes`) или останется (`No`).

### 1.3. Набор данных

- **Источник:** Telco Customer Churn, IBM Sample Data Sets —
  [файл `Telco-Customer-Churn.csv`](https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv).
  Локальная копия лежит в `data/Telco-Customer-Churn.csv`.
- **Объём:** 7 043 клиента, 21 столбец.
- **Признаки:**
  - демография — `gender`, `SeniorCitizen`, `Partner`, `Dependents`;
  - услуги — `PhoneService`, `MultipleLines`, `InternetService`, `OnlineSecurity`,
    `OnlineBackup`, `DeviceProtection`, `TechSupport`, `StreamingTV`, `StreamingMovies`;
  - договор и оплата — `Contract`, `PaperlessBilling`, `PaymentMethod`;
  - числовые показатели — `tenure` (стаж в месяцах), `MonthlyCharges` (ежемесячный платёж),
    `TotalCharges` (сумма всех платежей).
- **Целевая переменная:** `Churn` (`Yes` / `No`).
- **Почему этот датасет:** он открытый и не содержит персональных данных (имён, адресов,
  телефонов; `customerID` — случайный идентификатор, его мы удалим). В нём одновременно есть
  пропуски, категориальные и числовые признаки, то есть все этапы предобработки из задания
  становятся осмысленными.

### 1.4. Метрики

Базовой метрикой возьмём **accuracy** (доля верных ответов), как требует задание. Но классы
несбалансированы — уходит примерно каждый четвёртый клиент, — поэтому дополнительно
посчитаем **precision, recall, F1 и ROC-AUC** и сравним модель с «глупым» baseline.
""")

md("""
## 2. Импорт библиотек

Импортируем pandas и NumPy для работы с таблицами и вычислений, модули scikit-learn для
разделения выборки, масштабирования, обучения модели и расчёта метрик. Константа
`RANDOM_STATE = 42` фиксирует генератор случайных чисел, чтобы результат воспроизводился
при повторном запуске.
""")

code("""
import numpy as np
import pandas as pd
import sklearn
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.dummy import DummyClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)

pd.set_option("display.max_columns", 50)
RANDOM_STATE = 42

print("pandas       ", pd.__version__)
print("numpy        ", np.__version__)
print("scikit-learn ", sklearn.__version__)
""")

md("""
## 3. Загрузка данных

Читаем CSV в `DataFrame` функцией `pd.read_csv()` и смотрим на первые пять строк, чтобы
убедиться, что разделитель определился верно, а значения выглядят ожидаемо.
""")

code("""
DATA_PATH = "data/Telco-Customer-Churn.csv"

df = pd.read_csv(DATA_PATH)
print(f"Размер таблицы: {df.shape[0]} строк, {df.shape[1]} столбцов")
df.head()
""")

md("""
Метод `info()` показывает типы столбцов и количество непустых значений. Обратите внимание:
у `TotalCharges` тип `object` (строка), хотя это сумма платежей — значит, колонку придётся
приводить к числу.
""")

code("""
df.info()
""")

md("""
`info()` отчитался о 7 043 непустых значениях в каждом столбце, но это не гарантия
отсутствия пропусков: в `TotalCharges` часть значений записана пробелом, а не пустой
ячейкой, поэтому `isna()` их пока не видит. Это типичная ловушка реальных данных.

Посмотрим на баланс целевой переменной.
""")

code("""
print("Абсолютные значения:")
print(df["Churn"].value_counts())
print()
print("Доли, %:")
print((df["Churn"].value_counts(normalize=True) * 100).round(2))
""")

md("""
Классы несбалансированы: 73,46% клиентов остаются, 26,54% уходят. Это значит, что
accuracy 73,5% достигается моделью, которая всегда отвечает «не уйдёт». Поэтому одной
accuracy для вывода недостаточно — нужен baseline и метрики по классу «уйдёт».
""")

md("""
## 4. Предобработка данных

### 4.1. Пропуски, дубликаты и типы

Проверяем явные пропуски (`isna()`), дубликаты строк и повторы `customerID`, затем
преобразуем `TotalCharges` в число: всё, что не является числом (пробелы), станет `NaN`
и станет видимым.
""")

code("""
na_counts = df.isna().sum()
print("Явные пропуски NaN по столбцам (ненулевые):")
print(na_counts[na_counts > 0] if (na_counts > 0).any() else "нет")
print()
print("Дубликаты строк:", int(df.duplicated().sum()))
print("Повторы customerID:", int(df["customerID"].duplicated().sum()))

df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
missing_total = df["TotalCharges"].isna()
print()
print("TotalCharges после to_numeric — пропусков:", int(missing_total.sum()))
print(df.loc[missing_total, ["tenure", "MonthlyCharges", "TotalCharges", "Churn"]])
""")

md("""
Дубликатов и повторяющихся идентификаторов нет. После приведения к числу нашлось **11
пропусков** в `TotalCharges` (0,16% строк), и у всех этих клиентов `tenure = 0` — это
новые абоненты, которые ещё не получили ни одного счёта.

Как поступить с пропусками:

- **заполнить медианой** (~1 394) — но тогда у клиента с нулевым стажем появится
  «накопленный платёж» в 1 394, чего не бывает. Это ловушка: формально пропуск закрыт,
  но наблюдение искажено;
- **удалить строки** — допустимо, но мы потеряем часть данных и не сможем использовать
  этих клиентов при обучении;
- **заполнить нулём** — `tenure = 0` означает, что клиент ещё не пользовался услугами
  и накопленных платежей у него действительно нет, поэтому 0 — логичное значение.

Выбираем заполнение нулём: оно не создаёт искажённого наблюдения и сохраняет все 7 043
строки. Решение фиксируем явно, чтобы его можно было воспроизвести.
""")

code("""
df["TotalCharges"] = df["TotalCharges"].fillna(0)

print(f"Строк в таблице:     {len(df)}")
print(f"Заполнено нулём:     {int(missing_total.sum())}")
print("Осталось пропусков:", int(df.isna().sum().sum()))
""")

md("""
### 4.2. Выбросы

Проверим числовые признаки правилом 1,5 интерквартильного размаха (IQR): значения ниже
`Q1 − 1,5·IQR` или выше `Q3 + 1,5·IQR` считаются выбросами. Дополнительно посмотрим
описательные статистики.
""")

code("""
numeric_cols = ["tenure", "MonthlyCharges", "TotalCharges"]

outlier_report = []
for col in numeric_cols:
    q1, q3 = df[col].quantile([0.25, 0.75])
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    n_out = int(((df[col] < lower) | (df[col] > upper)).sum())
    outlier_report.append(
        {
            "признак": col,
            "Q1": round(q1, 2),
            "Q3": round(q3, 2),
            "нижняя граница": round(lower, 2),
            "верхняя граница": round(upper, 2),
            "выбросов": n_out,
        }
    )

pd.DataFrame(outlier_report)
""")

md("""
Дополним картину описательными статистиками: они показывают реальный диапазон значений
и помогают понять, насколько границы IQR соответствуют данным.
""")

code("""
df[numeric_cols].describe().round(2)
""")

md("""
По правилу 1,5·IQR выбросов нет ни в одном числовом признаке: границы шире реального
диапазона значений. Большие суммы `TotalCharges` (до 8 684) — это не ошибки, а клиенты
с длинным стажем и дорогим тарифом, поэтому удалять или «обрезать» их нельзя: мы потеряли
бы платёжеспособных клиентов. Оставляем данные как есть.
""")

md("""
### 4.3. Целевая переменная и матрица признаков

Кодируем `Churn` в 0/1: `No → 0`, `Yes → 1`. Колонку `customerID` удаляем — это
идентификатор, а не признак: у него 7 043 уникальных значения, и модель могла бы
«запоминать» клиентов вместо того, чтобы искать закономерности. Все остальные колонки
складываем в `X`, целевую — в `y`.
""")

code("""
y = df["Churn"].map({"No": 0, "Yes": 1})
X = df.drop(columns=["customerID", "Churn"])

print("y — распределение:", y.value_counts().sort_index().to_dict())
print("X — размер матрицы признаков:", X.shape)
print(f"Доля оттока: {y.mean() * 100:.2f}%")
""")

md("""
### 4.4. Разделение на обучающую и тестовую выборки

Делим данные в пропорции 80/20: 80% — обучение, 20% — проверка на данных, которые модель
не видела. Параметр `random_state=42` фиксирует разбиение, а `stratify=y` сохраняет долю
оттока одинаковой в обеих частях — иначе при дисбалансе можно случайно получить очень
разные по составу выборки.
""")

code("""
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
)

print(f"X_train: {X_train.shape}, X_test: {X_test.shape}")
print(f"y_train: {y_train.shape}, y_test: {y_test.shape}")
print(f"Доля оттока в train: {y_train.mean() * 100:.2f}%")
print(f"Доля оттока в test:  {y_test.mean() * 100:.2f}%")
""")

md("""
### 4.5. Масштабирование числовых признаков

`tenure`, `MonthlyCharges` и `TotalCharges` имеют разный масштаб (месяцы против тысяч
рублей). Логистическая регрессия с оптимизатором `lbfgs` на несмасштабированных данных
сходится медленно и может выдать предупреждение о недостижении сходимости. Поэтому
стандартизируем числовые признаки: вычитаем среднее и делим на стандартное отклонение.

Важно: `StandardScaler` обучаем **только на train** (`.fit_transform`), а к тесту
применяем уже найденные параметры (`.transform`). Иначе среднее и разброс «подсмотрят»
тестовую выборку — это утечка данных.
""")

code("""
scaler = StandardScaler()

X_train = X_train.copy()
X_test = X_test.copy()

X_train[numeric_cols] = scaler.fit_transform(X_train[numeric_cols])
X_test[numeric_cols] = scaler.transform(X_test[numeric_cols])

X_train[numeric_cols].describe().round(3)
""")

md("""
### 4.6. Кодирование категориальных признаков

Текстовые колонки нужно превратить в числа. Используем `pd.get_dummies()` (one-hot
кодирование), а не `LabelEncoder`: почти все категориальные признаки здесь **номинальные**
(`Contract`, `PaymentMethod`, `InternetService` и т. п.), между их значениями нет порядка.
`LabelEncoder` присвоил бы им числа 0, 1, 2, и модель восприняла бы это как «больше/меньше»,
что неверно.

Параметр `drop_first=True` убирает первый уровень каждой категории: информация о нём
восстанавливается из остальных, а лишняя колонка создаёт мультиколлинеарность («ловушка
фиктивных переменных»).

Кодирование выполняем **после** разделения и отдельно для train и test. Затем выравниваем
набор столбцов теста по train (`reindex`): если в тесте какой-то уровень не встретился,
колонка получит 0, и размерности совпадут.
""")

code("""
X_train = pd.get_dummies(X_train, drop_first=True, dtype=int)
X_test = pd.get_dummies(X_test, drop_first=True, dtype=int)
X_test = X_test.reindex(columns=X_train.columns, fill_value=0)

print("Признаков после кодирования:", X_train.shape[1])
print("Формы train/test:", X_train.shape, X_test.shape)
print("Столбцы совпадают:", list(X_train.columns) == list(X_test.columns))
print("Пропусков в train/test:", int(X_train.isna().sum().sum()), int(X_test.isna().sum().sum()))
print("Типы значений:", X_train.dtypes.value_counts().to_dict())
""")

md("""
Итог предобработки: 30 числовых признаков, пропусков нет, категории закодированы one-hot,
числовые стандартизированы. Теперь данные готовы к обучению.
""")

md("""
## 5. Обучение модели

### 5.1. Выбор и создание модели

Задача — бинарная классификация, поэтому берём **логистическую регрессию**
(`LogisticRegression`). Она подходит для базовой модели: быстро обучается, устойчива на
небольших табличных данных и интерпретируема — по коэффициентам видно направление влияния
каждого признака. Параметр `max_iter=1000` даёт оптимизатору достаточный запас итераций
(фактически нужно около 40), `random_state` фиксирует воспроизводимость.

Создаём объект модели, но пока не обучаем.
""")

code("""
model = LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)
model
""")

md("""
### 5.2. Обучение методом `.fit()`

Передаём модели только обучающую часть — `X_train` и `y_train`. Метод `.fit()` подбирает
коэффициенты так, чтобы минимизировать ошибку логистической функции потерь. Тестовая
выборка в обучении не участвует.
""")

code("""
model.fit(X_train, y_train)

print("Модель обучена")
print("Число признаков:", model.n_features_in_)
print("Итераций оптимизатору потребовалось:", int(model.n_iter_[0]))
""")

md("""
### 5.3. Предсказания методом `.predict()`

Метод `.predict()` возвращает класс (0 или 1) для каждого объекта теста. Дополнительно
берём `.predict_proba()[:, 1]` — вероятность оттока: она понадобится для ROC-AUC и позже
для подбора порога.
""")

code("""
y_pred = model.predict(X_test)
y_proba = model.predict_proba(X_test)[:, 1]

print("Получено предсказаний:", len(y_pred))
print("Первые 10 прогнозов:", y_pred[:10])
print("Первые 10 вероятностей:", np.round(y_proba[:10], 3))
""")

md("""
## 6. Оценка качества

### 6.1. Accuracy

`accuracy_score` — доля объектов, для которых прогноз совпал с фактом. Считаем её на
тестовой выборке: `y_test` — реальные ответы, `y_pred` — прогнозы модели.
""")

code("""
accuracy = accuracy_score(y_test, y_pred)
print(f"Accuracy на тестовой выборке: {accuracy:.4f} ({accuracy * 100:.2f}%)")
print(f"Верных ответов: {int(accuracy * len(y_test))} из {len(y_test)}")
""")

md("""
### 6.2. Дополнительные метрики

Accuracy не показывает, как модель ведёт себя с меньшим классом. Считаем:

- **precision** — из тех, кого модель назвала уходящими, какая доля действительно ушла;
- **recall** — какую долю реально ушедших клиентов модель нашла;
- **F1** — среднее гармоническое precision и recall;
- **ROC-AUC** — насколько хорошо модель ранжирует клиентов по вероятности оттока
  независимо от выбранного порога (0,5 — случайно, 1,0 — идеально).

Матрица ошибок показывает абсолютные числа: TN, FP, FN, TP.
""")

code("""
precision = precision_score(y_test, y_pred)
recall = recall_score(y_test, y_pred)
f1 = f1_score(y_test, y_pred)
roc_auc = roc_auc_score(y_test, y_proba)

print(f"Precision: {precision:.4f}")
print(f"Recall:    {recall:.4f}")
print(f"F1:        {f1:.4f}")
print(f"ROC-AUC:   {roc_auc:.4f}")
print()
print("Матрица ошибок [[TN, FP], [FN, TP]]:")
print(confusion_matrix(y_test, y_pred))
print()
print("Отчёт по классам:")
print(classification_report(y_test, y_pred, target_names=["останется (0)", "уйдёт (1)"]))
""")

md("""
### 6.3. Сравнение факта и прогноза

Выводим первые 15 объектов теста рядом: факт, прогноз и вероятность оттока. Так видно,
на каких клиентах модель уверена, а где ошибается и насколько уверенно.
""")

code("""
comparison = pd.DataFrame(
    {
        "y_test (факт)": y_test.head(15).values,
        "y_pred (прогноз)": y_pred[:15],
        "вероятность оттока": np.round(y_proba[:15], 3),
    }
)
comparison["совпало"] = comparison["y_test (факт)"] == comparison["y_pred (прогноз)"]
comparison
""")

md("""
### 6.4. Проверка на вырожденное поведение

Главная проверка из задания: модель не должна выдавать одно и то же значение для всех
объектов. Смотрим распределение прогнозов и число уникальных классов. Для контраста обучаем
`DummyClassifier(strategy="most_frequent")` — он всегда предсказывает самый частый класс
(«не уйдёт») и показывает, какую accuracy даёт полностью вырожденная модель.
""")

code("""
pred_distribution = pd.Series(y_pred).value_counts().sort_index()
print("Распределение прогнозов модели:")
print(pred_distribution.to_dict())
print("Уникальные значения в y_pred:", np.unique(y_pred))
print()

dummy = DummyClassifier(strategy="most_frequent")
dummy.fit(X_train, y_train)
dummy_pred = dummy.predict(X_test)
dummy_accuracy = accuracy_score(y_test, dummy_pred)

print("DummyClassifier (всегда «не уйдёт»):")
print("  уникальные значения:", np.unique(dummy_pred))
print(f"  accuracy: {dummy_accuracy:.4f}")
print()
print(f"Прирост accuracy логистической регрессии над baseline: {accuracy - dummy_accuracy:+.4f}")
""")

md("""
Проверка пройдена: модель предсказывает **оба класса** — 1 092 «останется» и 317 «уйдёт»,
то есть поведение не вырождено. DummyClassifier выдаёт только нули и всё равно получает
accuracy 73,5% — именно поэтому высокая accuracy сама по себе ничего не доказывает.
Наша модель выше baseline на 7,2 п.п. и при этом реально разделяет клиентов.
""")

md("""
### 6.5. Какие признаки сильнее всего влияют на прогноз

После стандартизации коэффициенты логистической регрессии можно сравнивать между собой:
положительный коэффициент повышает вероятность оттока, отрицательный — снижает. Смотрим
по пять самых сильных признаков в каждую сторону.
""")

code("""
coefficients = pd.Series(model.coef_[0], index=X_train.columns).sort_values()

print("Снижают вероятность оттока (сильнее всего):")
print(coefficients.head(5).round(3))
print()
print("Повышают вероятность оттока (сильнее всего):")
print(coefficients.tail(5).round(3))
""")

md("""
Интерпретация согласуется со здравым смыслом: длительный стаж (`tenure`) и долгосрочный
контракт (`Contract_Two year`) снижают риск ухода, а оптоволоконный интернет
(`InternetService_Fiber optic`) и оплата электронным чеком (`PaymentMethod_Electronic check`)
его повышают. Коэффициенты `tenure` и `TotalCharges` смотрят в разные стороны, потому что
эти признаки сильно коррелируют между собой (стаж и накопленная сумма) — на качестве
прогноза это не сказывается, но трактовать их по отдельности нужно осторожно.
""")

md("""
### 6.6. Вариант с учётом дисбаланса классов

Проверим, что даст `class_weight="balanced"`: он велит модели штрафовать ошибки на редком
классе сильнее, чтобы чаще находить уходящих клиентов. Это не обязательный шаг задания,
а дополнительный эксперимент — он показывает цену выбора метрики при дисбалансе.
""")

code("""
model_balanced = LogisticRegression(
    max_iter=1000, random_state=RANDOM_STATE, class_weight="balanced"
)
model_balanced.fit(X_train, y_train)
y_pred_balanced = model_balanced.predict(X_test)
y_proba_balanced = model_balanced.predict_proba(X_test)[:, 1]

balanced_metrics = {
    "accuracy": accuracy_score(y_test, y_pred_balanced),
    "precision": precision_score(y_test, y_pred_balanced),
    "recall": recall_score(y_test, y_pred_balanced),
    "f1": f1_score(y_test, y_pred_balanced),
    "roc_auc": roc_auc_score(y_test, y_proba_balanced),
}

comparison_models = pd.DataFrame(
    {
        "LogisticRegression": {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "roc_auc": roc_auc,
        },
        "LogisticRegression (balanced)": balanced_metrics,
    }
).round(4)

print("Прогнозы balanced-модели:", pd.Series(y_pred_balanced).value_counts().sort_index().to_dict())
print()
comparison_models
""")

md("""
Balanced-модель находит 293 ушедших клиента из 374 (recall 0,78 против 0,56), но платит
за это точностью: precision падает до 0,50, а accuracy — до 0,74, то есть почти до уровня
«глупого» baseline (73,5%). ROC-AUC у обеих моделей практически одинаков (0,84), потому что
способность ранжировать клиентов не изменилась — изменился только порог принятия решения.

Это важный вывод: при дисбалансе выбор метрики зависит от бизнес-цели. Если дороже
пропустить уходящего клиента — нужен высокий recall и balanced-вариант. Если дороже зря
беспокоить лояльных — нужен высокий precision и базовая модель. Accuracy здесь —
вспомогательная метрика.
""")

md("""
## 7. Итоговый вывод

**Какая модель использовалась.** Логистическая регрессия
`LogisticRegression(max_iter=1000, random_state=42)` из scikit-learn. После предобработки
получилось 30 числовых признаков: числовые стандартизированы, категориальные закодированы
one-hot без первого уровня. Обучение — на 5 634 объектах, проверка — на 1 409 объектах,
которых модель не видела.

**Какие метрики получены.**

| Метрика | Значение |
|---|---|
| Accuracy | **0,8062** |
| Precision (класс «уйдёт») | 0,6593 |
| Recall (класс «уйдёт») | 0,5588 |
| F1 (класс «уйдёт») | 0,6049 |
| ROC-AUC | 0,8422 |

Матрица ошибок: 927 верно предсказанных «останется», 209 верно предсказанных «уйдёт»,
108 ложных «уйдёт» и 165 пропущенных оттоков.

**Хороший ли это результат и почему.** Для базовой модели — да. Accuracy 80,6% на 7,2
п.п. выше «глупого» baseline, который всегда отвечает «не уйдёт» (73,5%).
ROC-AUC 0,84 означает, что модель уверенно ранжирует клиентов по склонности к оттоку:
0,5 — случайное угадывание, 1,0 — идеальное разделение. Модель не вырождена: она
предсказывает оба класса (1 092 «останется» и 317 «уйдёт»), а не одно значение для всех.

При этом модель не готова к продакшену «как есть». Recall 0,56: из 374 реально ушедших
клиентов модель нашла только 209 — около 44% оттока пропущено, а именно эти клиенты и нужны
бизнесу для удержания. Precision 0,66: примерно треть клиентов, которых модель считает
уходящими, на самом деле остаются — лишние затраты на удержание. Вариант с
`class_weight="balanced"` поднимает recall до 0,78 (находит 293 из 374), но роняет precision
до 0,50 и accuracy до 0,74 — почти до уровня baseline. Это наглядно показывает, почему при
дисбалансе классов нельзя смотреть только на accuracy: метрику нужно выбирать под
бизнес-цель.

**Вывод.** Логистическая регрессия подходит как интерпретируемая базовая модель: она
значимо лучше вырожденного прогноза и хорошо разделяет классы (ROC-AUC 0,84). Для
практического применения нужно:

1. подобрать порог классификации или `class_weight` под стоимость пропущенного оттока
   и ложного срабатывания;
2. добавить кросс-валидацию и сравнить с градиентным бустингом (XGBoost / LightGBM);
3. проверить стабильность на новых периодах.

В текущем виде модель полезна как baseline и как инструмент анализа факторов оттока.
""")

md("""
## 8. Самопроверка по критериям задания

| Критерий | Где выполнен | Статус |
|---|---|---|
| Выбран датасет, выполнена предобработка: пропуски, выбросы, кодирование категорий | разделы 1, 4.1–4.6 | ✅ |
| Данные разделены на train/test (`train_test_split`, `random_state=42`) | раздел 4.4 | ✅ |
| Модель обучена через `.fit()`, предсказания получены через `.predict()` | разделы 5.2–5.3 | ✅ |
| Рассчитана метрика качества и объяснено её значение | разделы 6.1–6.2, 7 | ✅ |
| Проверено отсутствие вырожденного поведения | раздел 6.4 | ✅ |
| Сформулирован вывод о пригодности модели | раздел 7 | ✅ |
| Ноутбук выполняется целиком без ошибок (Restart & Run All) | проверено сборщиком `tools/build_notebook.py` | ✅ |
| Перед каждой ячейкой кода есть пояснение в Markdown | все разделы | ✅ |
""")

md("""
## 9. Как воспроизвести результат

1. Установить зависимости: `pip install pandas numpy scikit-learn notebook`.
2. Открыть `Практика_обучения_модели.ipynb` из этой папки (рядом должна лежать папка `data/`).
3. Выполнить **Restart & Run All** — notebook сам скачивать данные не будет, используется
   локальная копия `data/Telco-Customer-Churn.csv`.

Альтернативно: `python -I tools/build_notebook.py` — скрипт заново соберёт ноутбук и
выполнит все ячейки.
""")

# --------------------------------------------------------------------------
notebook = nbf.v4.new_notebook(cells=cells)
notebook.metadata = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "version": "3.14.3"},
}

os.chdir(BASE)
client = NotebookClient(
    notebook,
    timeout=600,
    kernel_name="python3",
    resources={"metadata": {"path": str(BASE)}},
)
client.execute()
nbf.write(notebook, NOTEBOOK_PATH)

code_cells = [c for c in notebook.cells if c.cell_type == "code"]
errors = [
    out
    for c in code_cells
    for out in c.get("outputs", [])
    if out.get("output_type") == "error"
]
print(f"Ноутбук сохранён: {NOTEBOOK_PATH}")
print(f"Ячеек: {len(notebook.cells)} (код: {len(code_cells)}, markdown: {len(notebook.cells) - len(code_cells)})")
print(f"Ошибок выполнения: {len(errors)}")
if errors:
    raise SystemExit(1)
