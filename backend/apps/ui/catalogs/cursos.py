import json
from pathlib import Path


def load_cursos():
    p = Path(__file__).resolve().parent / "cursos.json"
    return json.loads(p.read_text(encoding="utf-8"))
