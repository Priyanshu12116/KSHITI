"""Ask Kshiti from the terminal: python tools/ask.py "your question" """
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kshiti.pipeline import run  # noqa: E402

if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "My house faces a 10 m wide street and will be 9 m tall. How much open space do I leave at the front?"
    r = run(q, on_event=lambda kind, data: print(data, end="", flush=True) if kind == "text" else None)
    print("\n\n" + r.model_dump_json(indent=2))
