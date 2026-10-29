"""Встраивает сохранённые PNG-графики в выводы соответствующих ячеек ноутбука.

При выполнении с backend'ом Agg `plt.show()` не создаёт inline-изображение,
поэтому графики, сохранённые в reports/, добавляются в outputs ноутбука здесь.
"""
import base64
from pathlib import Path

import nbformat as nbf

BASE = Path(__file__).resolve().parent
NB_PATH = BASE / "Практика_pipeline.ipynb"
PLOTS = [
    "target_distribution.png",
    "eda_money_hour.png",
    "model_comparison.png",
    "optuna_history.png",
    "feature_importance.png",
]

nb = nbf.read(NB_PATH, as_version=4)
embedded = 0
for cell in nb.cells:
    if cell.cell_type != "code":
        continue
    for png in PLOTS:
        if f'"{png}"' not in cell.source:
            continue
        has_image = any("image/png" in out.get("data", {}) for out in cell.get("outputs", []))
        if has_image:
            continue
        path = BASE / "reports" / png
        if not path.exists():
            print("нет файла:", path)
            continue
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        cell.outputs.append(
            nbf.v4.new_output(
                "display_data",
                data={"image/png": encoded, "text/plain": f"<Figure: {png}>"},
                metadata={"image/png": {"width": 900}},
            )
        )
        embedded += 1

nbf.write(nb, NB_PATH)
print("Встроено графиков:", embedded)
