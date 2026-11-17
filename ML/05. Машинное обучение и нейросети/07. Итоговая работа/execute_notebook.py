# -*- coding: utf-8 -*-
"""Выполнение ноутбука целиком (аналог Kernel -> Restart and Run All)."""
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).parent
NB = ROOT / "notebook.ipynb"

nb = nbformat.read(NB, as_version=4)
client = NotebookClient(
    nb,
    timeout=1800,
    kernel_name="python3",
    resources={"metadata": {"path": str(ROOT)}},
    allow_errors=False,
)
client.execute()
nbformat.write(nb, NB)
print("Ноутбук выполнен без ошибок и сохранён с выводами:", NB)
