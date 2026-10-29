"""Выполнение ноутбука Практика_pipeline.ipynb через nbclient."""
from pathlib import Path

import nbformat
from nbclient import NotebookClient

BASE = Path(__file__).resolve().parent
NB_PATH = BASE / "Практика_pipeline.ipynb"

nb = nbformat.read(NB_PATH, as_version=4)
client = NotebookClient(
    nb,
    timeout=3600,
    kernel_name="python3",
    resources={"metadata": {"path": str(BASE)}},
    allow_errors=False,
)
client.execute()
nbformat.write(nb, NB_PATH)
print("Ноутбук выполнен:", NB_PATH)
print("Ячеек:", len(nb.cells))
