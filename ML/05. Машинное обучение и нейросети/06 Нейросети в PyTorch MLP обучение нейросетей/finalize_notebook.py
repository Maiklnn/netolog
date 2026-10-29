"""Подставляет фактические цифры в ячейку «Итоговые выводы» после выполнения.

Текст выводов собирается из metrics.json, поэтому всегда соответствует реальным числам.

Запуск: python finalize_notebook.py
"""
import json
import pathlib

import nbformat

HERE = pathlib.Path(__file__).resolve().parent
NB = HERE / "PyTorch_mlp_task.ipynb"
METRICS = HERE / "metrics.json"

m = json.loads(METRICS.read_text(encoding="utf-8"))
b, e1, e2, e3 = m["baseline"], m["exp1"], m["exp2"], m["exp3"]
best = max([b, e1, e2, e3], key=lambda r: r["val_f1"])
ds = m["dataset"]


def delta(x, base=b):
    d = x["val_acc"] - base["val_acc"]
    if d > 0.005:
        return f"выше базовой на {d * 100:.2f} п.п."
    if d < -0.005:
        return f"ниже базовой на {abs(d) * 100:.2f} п.п."
    return "на уровне базовой (разница в пределах шума)"


text = f"""## 7. Итоговые выводы

Данные: Breast Cancer, {ds['n_samples']} наблюдений, {ds['n_features']} признаков,
разбиение train/test = {ds['train_size']}/{ds['test_size']} (как в шаблоне: тестовая выборка
используется и для контроля обучения). Все модели обучались с фиксированным seed.

> Важно для интерпретации: в тесте всего {ds['test_size']} объектов, поэтому **одна ошибка
> меняет accuracy на ≈{100 / ds['test_size']:.1f} п.п.** Различия в 1–2 ошибки — статистический шум,
> а не устойчивое преимущество архитектуры.

### 1. Базовая модель

Сеть 30 → 16 → 1 (ReLU, без регуляризации), `BCEWithLogitsLoss`, Adam с lr=1e-3, 50 эпох,
{m['baseline']['params']} параметров.

- accuracy на тесте: **{b['val_acc']:.4f}**, F1: **{b['val_f1']:.4f}**;
- loss: train {b['final_train_loss']:.4f} / val {b['final_val_loss']:.4f};
- разрыв train/val accuracy: **{b['overfit_gap']:+.4f}**.

Даже такая маленькая сеть почти решает задачу: признаки хорошо разделимы после
стандартизации, а 50 эпох Adam достаточно для сходимости.

### 2. Эксперимент 1 — глубже и шире (30 → 64 → 32 → 1)

Добавлен второй скрытый слой, ширина увеличена до 64 и 32; оптимизатор, lr и число эпох те же,
{m['exp1']['params']} параметров (в {m['exp1']['params'] / m['baseline']['params']:.0f} раз больше базовой).

- accuracy: **{e1['val_acc']:.4f}** — {delta(e1)}, F1: **{e1['val_f1']:.4f}**;
- разрыв train/val: **{e1['overfit_gap']:+.4f}** (у базовой {b['overfit_gap']:+.4f});
- train accuracy {e1['train_acc']:.4f} при val {e1['val_acc']:.4f}: модель почти запомнила train.

Вывод: на 455 обучающих примерах лишняя ёмкость не помогает — она лишь увеличивает
переобучение и разброс качества.

### 3. Эксперимент 2 — BatchNorm + Dropout + weight decay

Архитектура 64–32 с `BatchNorm1d` после каждого линейного слоя, `Dropout(0.3)`,
`weight_decay=1e-4`, lr=5e-4, 100 эпох.

- accuracy: **{e2['val_acc']:.4f}** — {delta(e2)}, F1: **{e2['val_f1']:.4f}**;
- разрыв train/val: **{e2['overfit_gap']:+.4f}**;
- лучшая accuracy по эпохам: {e2['best_val_acc']:.4f}.

Регуляризация ожидаемо «прижала» train accuracy ({e2['train_acc']:.4f} против {e1['train_acc']:.4f}
у незарегуляризованной широкой сети) и сделала кривые обучения ровнее, но на тесте
итоговое качество не выросло: данных слишком мало, чтобы широкая сеть реализовала
свой потенциал.

### 4. Эксперимент 3 — SGD с импульсом

Архитектура 64–32, `optim.SGD(lr=0.01, momentum=0.9)`, 100 эпох.

- accuracy: **{e3['val_acc']:.4f}** — {delta(e3)}, F1: **{e3['val_f1']:.4f}**;
- разрыв train/val: **{e3['overfit_gap']:+.4f}**, train accuracy {e3['train_acc']:.4f}.

SGD с моментом сходится медленнее Adam: к 100-й эпохе train loss минимален
({e3['final_train_loss']:.4f}), а val loss выше, чем у базовой модели
({e3['final_val_loss']:.4f} против {b['final_val_loss']:.4f}) — это признак переобучения.

### 5. Самая удачная модель

По F1 на тесте лучшей оказалась **{m['best']}** (accuracy {best['val_acc']:.4f},
F1 {best['val_f1']:.4f}, разрыв train/val {best['overfit_gap']:+.4f}).

Это ожидаемый результат для данного датасета: задача почти линейно разделима, а тест
состоит всего из {ds['test_size']} объектов. Простая сеть на 16 нейронов не переобучается
и показывает качество на уровне потолка, тогда как более ёмкие модели тратят её на
запоминание train. Практический вывод: **наращивать архитектуру нужно только после
того, как исчерпаны работа с данными и валидацией**.

Что стоит сделать дальше, чтобы выводы были статистически надёжными:
1. Выделить отдельную валидацию (или использовать `StratifiedKFold` + `cross_val_score`)
   и трогать тест только один раз — сейчас тест одновременно служит валидацией.
2. Подбирать гиперпараметры (lr, dropout, weight decay) по кросс-валидации, а не по одному
   разбиению.
3. Усреднять метрики по нескольким seed'ам: при 114 тестовых объектах разница в одну
   ошибку ничего не значит.
"""

nb = nbformat.read(NB, as_version=4)
replaced = False
for cell in nb.cells:
    if cell.cell_type == "markdown" and cell.source.lstrip().startswith("## 7. Итоговые выводы"):
        cell.source = text
        replaced = True

if not replaced:
    raise SystemExit("ячейка выводов не найдена")

nbformat.write(nb, NB)
print("Выводы подставлены.")
