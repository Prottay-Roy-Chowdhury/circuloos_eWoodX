"""
Independent OpenCV viewer for testing native
Windows window embedding in the eWoodX app.
"""

import sys
import time
import math

import cv2
import numpy as np


WINDOW_NAME = "eWoodX OpenCV Test Viewer"

WIDTH = 960
HEIGHT = 540


def main() -> None:

    cv2.namedWindow(
        WINDOW_NAME,
        cv2.WINDOW_NORMAL,
    )

    cv2.resizeWindow(
        WINDOW_NAME,
        WIDTH,
        HEIGHT,
    )

    start_time = time.perf_counter()

    frame_count = 0
    paused = False

    frame = np.zeros(
        (HEIGHT, WIDTH, 3),
        dtype=np.uint8,
    )

    print(
        "[VIEWER] OpenCV viewer started.",
        flush=True,
    )

    try:

        while True:

            if not paused:

                elapsed = (
                    time.perf_counter()
                    - start_time
                )

                frame[:] = (35, 35, 35)

                # Workspace boundary
                cv2.rectangle(
                    frame,
                    (40, 80),
                    (WIDTH - 40, HEIGHT - 60),
                    (120, 120, 120),
                    2,
                )

                # Animated timber geometry
                for index in range(3):

                    offset = int(
                        15 * math.sin(
                            elapsed * 2 + index
                        )
                    )

                    x = 180 + index * 250
                    y = 130 + offset

                    cv2.rectangle(
                        frame,
                        (x, y),
                        (x + 130, y + 280),
                        (90, 145, 185),
                        -1,
                    )

                    cv2.rectangle(
                        frame,
                        (x, y),
                        (x + 130, y + 280),
                        (80, 230, 120),
                        2,
                    )

                    cv2.circle(
                        frame,
                        (x + 65, y + 80),
                        15,
                        (35, 35, 35),
                        -1,
                    )

                    cv2.putText(
                        frame,
                        f"Timber {index + 1}",
                        (x + 10, y + 160),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (255, 255, 255),
                        1,
                    )

                cv2.putText(
                    frame,
                    "eWoodX - OpenCV Embedding Test",
                    (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 255, 255),
                    2,
                )

                cv2.putText(
                    frame,
                    f"Frame: {frame_count}",
                    (40, HEIGHT - 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    1,
                )

                cv2.putText(
                    frame,
                    "SPACE: Pause | Q: Quit",
                    (WIDTH - 330, HEIGHT - 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (200, 200, 200),
                    1,
                )

                frame_count += 1

            cv2.imshow(
                WINDOW_NAME,
                frame,
            )

            key = cv2.waitKey(16) & 0xFF

            if key == ord("q") or key == 27:
                break

            if key == ord(" "):

                paused = not paused

                print(
                    f"[VIEWER] Paused: {paused}",
                    flush=True,
                )

            # Allow graceful shutdown from the app.
            # The app sends a native WM_CLOSE message.
            try:

                visible = cv2.getWindowProperty(
                    WINDOW_NAME,
                    cv2.WND_PROP_VISIBLE,
                )

                if visible < 1:
                    break

            except cv2.error:
                break

    except KeyboardInterrupt:

        print(
            "[VIEWER] Shutdown requested.",
            flush=True,
        )

    finally:

        cv2.destroyAllWindows()

        print(
            "[VIEWER] OpenCV viewer stopped.",
            flush=True,
        )


if __name__ == "__main__":
    main()