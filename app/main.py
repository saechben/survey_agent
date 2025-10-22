from __future__ import annotations

from app.UI import run_app

import os
if os.getenv("DEBUG_ATTACH") == "1":
    import debugpy
    debugpy.listen(("localhost", 5678))
    print("✅ Waiting for debugger attach on port 5678...")
    debugpy.wait_for_client()
    print("✅ Debugger attached!")
def main() -> None:
    """Launch the Streamlit survey UI."""

    run_app()


if __name__ == "__main__":
    main()
