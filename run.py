"""Start Kshiti: python run.py  ->  http://localhost:8000"""
import os
import webbrowser

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    if os.environ.get("KSHITI_NO_BROWSER") != "1":
        webbrowser.open(f"http://localhost:{port}")
    uvicorn.run("app.server:app", host="127.0.0.1", port=port)
