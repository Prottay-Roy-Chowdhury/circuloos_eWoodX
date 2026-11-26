"""
Native Windows window embedding utilities
for the eWoodX application.
"""

from __future__ import annotations

import win32gui
import win32con
import win32process

from PySide6.QtCore import Qt
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QWidget


class NativeWindowEmbedder:

    def __init__(self) -> None:

        self.hwnd: int | None = None

        self.native_window: QWindow | None = None

        self.container: QWidget | None = None

        self.original_parent = None
        self.original_style = None

    # ---------------------------------------------------------
    # Window discovery
    # ---------------------------------------------------------

    @staticmethod
    def find_window(
        title: str,
        process_id: int | None = None,
    ) -> int | None:

        matches = []

        def callback(hwnd, _):

            if not win32gui.IsWindowVisible(hwnd):
                return True

            if win32gui.GetWindowText(hwnd) != title:
                return True

            if process_id is not None:

                _, window_pid = (
                    win32process.GetWindowThreadProcessId(
                        hwnd
                    )
                )

                if window_pid != process_id:
                    return True

            matches.append(hwnd)

            return True

        win32gui.EnumWindows(
            callback,
            None,
        )

        return matches[0] if matches else None

    # ---------------------------------------------------------
    # Embedding
    # ---------------------------------------------------------

    def embed(
        self,
        hwnd: int,
        parent: QWidget,
    ) -> QWidget:

        if not win32gui.IsWindow(hwnd):

            raise RuntimeError(
                "Invalid native window handle."
            )

        if self.container is not None:

            raise RuntimeError(
                "A window is already embedded."
            )

        self.hwnd = hwnd

        self.original_parent = (
            win32gui.GetParent(hwnd)
        )

        self.original_style = (
            win32gui.GetWindowLong(
                hwnd,
                win32con.GWL_STYLE,
            )
        )

        self.native_window = QWindow.fromWinId(
            hwnd
        )

        if self.native_window is None:

            self.hwnd = None

            raise RuntimeError(
                "Qt could not wrap the native window."
            )

        self.container = (
            QWidget.createWindowContainer(
                self.native_window,
                parent,
            )
        )

        self.container.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )

        self.container.setMinimumSize(
            320,
            180,
        )

        self.container.show()

        return self.container

    # ---------------------------------------------------------
    # Window state
    # ---------------------------------------------------------

    def is_valid(self) -> bool:

        return (
            self.hwnd is not None
            and bool(
                win32gui.IsWindow(self.hwnd)
            )
        )

    # ---------------------------------------------------------
    # Focus
    # ---------------------------------------------------------

    def focus(self) -> None:

        if not self.is_valid():
            return

        if self.container is not None:

            self.container.setFocus()

        if self.native_window is not None:

            self.native_window.requestActivate()

    # ---------------------------------------------------------
    # Shutdown request
    # ---------------------------------------------------------

    def request_close(self) -> None:

        if self.is_valid():

            win32gui.PostMessage(
                self.hwnd,
                win32con.WM_CLOSE,
                0,
                0,
            )

    # ---------------------------------------------------------
    # Cleanup
    # ---------------------------------------------------------

    def release(self) -> None:

        if self.native_window is not None:

            self.native_window.setParent(None)

        if self.is_valid():

            try:

                win32gui.SetParent(
                    self.hwnd,
                    self.original_parent or 0,
                )

                if self.original_style is not None:

                    win32gui.SetWindowLong(
                        self.hwnd,
                        win32con.GWL_STYLE,
                        self.original_style,
                    )

                win32gui.SetWindowPos(
                    self.hwnd,
                    0,
                    0,
                    0,
                    0,
                    0,
                    win32con.SWP_NOMOVE
                    | win32con.SWP_NOSIZE
                    | win32con.SWP_NOZORDER
                    | win32con.SWP_NOACTIVATE
                    | win32con.SWP_FRAMECHANGED,
                )

            except Exception as error:

                print(
                    f"[APP] Window release error: {error}"
                )

        if self.container is not None:

            self.container.hide()
            self.container.deleteLater()

        self.container = None
        self.native_window = None
        self.hwnd = None
        self.original_parent = None
        self.original_style = None