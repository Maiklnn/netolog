"""Выполняет PyTorch_mlp_task.ipynb на месте (nbclient, ядро python3).

Запуск: python execute_notebook.py
"""
import pathlib
import sys

import nbformat
from nbclient import NotebookClient

HERE = pathlib.Path(__file__).resolve().parent
NB = HERE / "PyTorch_mlp_task.ipynb"

nb = nbformat.read(NB, as_version=4)
client = NotebookClient(
    nb,
    timeout=900,
    kernel_name="python3",
    resources={"metadata": {"path": str(HERE)}},
)
client.execute()
nbformat.write(nb, NB)
print("Ноутбук выполнен:", NB)
