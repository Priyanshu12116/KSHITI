"""Check that both API keys in .env work. Run: python tools/check_keys.py"""
import os
import time

from dotenv import load_dotenv

load_dotenv()


def check_claude() -> str:
    import anthropic

    t = time.perf_counter()
    msg = anthropic.Anthropic().messages.create(
        model="claude-opus-5-5",
        max_tokens=64,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": "Reply with the single word: ready"}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    return f"Claude OK ({time.perf_counter() - t:.1f}s): {text}"


def check_cerebras() -> str:
    from cerebras.cloud.sdk import Cerebras

    t = time.perf_counter()
    out = Cerebras(api_key=os.environ["CEREBRAS_API_KEY"]).chat.completions.create(
        model="gpt-oss-120b",
        messages=[{"role": "user", "content": "Reply with the single word: ready"}],
    )
    return f"Cerebras OK ({time.perf_counter() - t:.1f}s): {out.choices[0].message.content.strip()}"


if __name__ == "__main__":
    for name, fn in [("ANTHROPIC_API_KEY", check_claude), ("CEREBRAS_API_KEY", check_cerebras)]:
        if not os.environ.get(name):
            print(f"MISSING {name} in .env")
            continue
        try:
            print(fn())
        except Exception as e:  # noqa: BLE001 - report any failure plainly
            print(f"FAILED {name}: {type(e).__name__}: {e}")
