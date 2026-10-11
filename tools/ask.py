"""Ask Kshiti from the terminal: python tools/ask.py "your question" """
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kshiti.engine import ask  # noqa: E402

if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "My house faces a 10 m wide street and will be 9 m tall. How much open space do I leave at the front?"
    a = ask(q, on_text=lambda t: print(t, end="", flush=True))
    print("\n\n" + a.model_dump_json(indent=2, exclude={"question"}))
