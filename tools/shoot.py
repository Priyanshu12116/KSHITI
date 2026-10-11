"""Visual QA: drive the interface in Microsoft Edge and save screenshots.

Needs the server running with KSHITI_DEV=1 (for fixtures):
  set KSHITI_DEV=1 && python run.py
Run: python tools/shoot.py [base_url]
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
import time
OUT = Path(__file__).resolve().parent.parent / "out" / "shots" / time.strftime("%H%M%S")
OUT.mkdir(parents=True, exist_ok=True)
print(OUT)


def main() -> None:
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        ctx = b.new_context(viewport={"width": 1366, "height": 768}, device_scale_factor=1)
        page = ctx.new_page()
        errors: list[str] = []
        page.on("console", lambda m: errors.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

        # 1. opening animation mid-draw and at the end
        page.goto(BASE)
        page.wait_for_timeout(900)
        page.screenshot(path=str(OUT / "01_splash_drawing.png"))
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / "02_splash_done.png"))
        page.wait_for_timeout(2200)
        page.screenshot(path=str(OUT / "03_home.png"))
        page.screenshot(path=str(OUT / "03b_home_full.png"), full_page=True)

        # 2. answered (fixture) states
        for name, q in [("headline", "My plot is 200 sq m on a 9 m road. How much gap do I leave at the front, how many floors can I build, and what fee do I pay?"),
                        ("hindi", "मेरा प्लॉट 200 वर्ग मीटर का है और सामने 9 मीटर चौड़ी सड़क है। आगे कितनी जगह खाली छोड़नी होगी?"),
                        ("amendment", "Do I need separate development permission for a 300 sq m plot that matches the Development Plan?"),
                        ("notfound", "How do I pay my property tax online?")]:
            page.goto(f"{BASE}/?nosplash=1&fixture={name}&q={q}")
            page.wait_for_timeout(3500)
            page.screenshot(path=str(OUT / f"10_{name}_full.png"), full_page=True)
            page.locator("#result").screenshot(path=str(OUT / f"11_{name}_result.png"))

        # 3. hindi interface + drawer
        page.goto(f"{BASE}/?nosplash=1&fixture=headline&q=My plot is 200 sq m on a 9 m road. How much gap do I leave at the front, how many floors can I build, and what fee do I pay?")
        page.wait_for_timeout(3500)
        page.click('.seg--lang [data-lang="hi"]')
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT / "20_ui_hindi_full.png"), full_page=True)
        page.click('.seg--lang [data-lang="en"]')
        page.click("#proof [data-rule]")
        page.wait_for_timeout(900)
        page.screenshot(path=str(OUT / "21_drawer.png"))
        page.keyboard.press("Escape")

        # 4. real API path with no key -> clear error state
        page.goto(f"{BASE}/?nosplash=1")
        page.fill("#q", "What is the fee for building permission for a residential house?")
        page.keyboard.press("Enter")
        page.wait_for_timeout(4000)
        page.screenshot(path=str(OUT / "30_no_key_error_full.png"), full_page=True)

        # 5. mobile
        m = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        mp = m.new_page()
        mp.goto(f"{BASE}/?nosplash=1&fixture=headline&q=My plot is 200 sq m on a 9 m road. How much gap do I leave at the front, how many floors can I build, and what fee do I pay?")
        mp.wait_for_timeout(3500)
        mp.screenshot(path=str(OUT / "40_mobile_full.png"), full_page=True)

        b.close()
        print("\n".join(errors) or "no console errors")


if __name__ == "__main__":
    main()
