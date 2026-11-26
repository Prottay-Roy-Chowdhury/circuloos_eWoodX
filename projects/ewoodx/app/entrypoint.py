"""
eWoodX operator application entrypoint.

Run from repository root:

    python -m projects.ewoodx.app.entrypoint
"""

import sys
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__).resolve().parents[3]
)

if str(PROJECT_ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from PySide6.QtWidgets import QApplication

from projects.ewoodx.app.main_window import (
    EWoodXMainWindow,
)


def main() -> None:

    print(
        "[APP] Initializing application.",
        flush=True,
    )

    app = QApplication(sys.argv)

    app.setApplicationName("eWoodX")

    app.setStyle("Fusion")

    app.setQuitOnLastWindowClosed(True)

    window = EWoodXMainWindow()

    window.show()

    print(
        "[APP] Qt event loop started.",
        flush=True,
    )

    exit_code = app.exec()

    print(
        f"[APP] Qt event loop finished. "
        f"Exit code: {exit_code}",
        flush=True,
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()