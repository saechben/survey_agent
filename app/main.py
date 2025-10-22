from __future__ import annotations
import os
if os.getenv("DEBUG_ATTACH") == "1":
    import debugpy

    if os.environ.get("DEBUGPY_LISTENING") != "1":
        debugpy.listen(("0.0.0.0", 5678))  
        os.environ["DEBUGPY_LISTENING"] = "1"
        print("✅ Waiting for debugger attach on port 5678...")

    if not debugpy.is_client_connected():
        debugpy.wait_for_client()
        print("✅ Debugger attached!")
from app.UI import run_app


def main() -> None:
    """Launch the Streamlit survey UI."""

    run_app()


if __name__ == "__main__":
    main()
