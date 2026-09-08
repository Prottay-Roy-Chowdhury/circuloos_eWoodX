"""
Real hardware test for ArducamCamera.
"""

from pathlib import Path
import sys

import cv2


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from framework.sensing import (
    ArducamCamera,
)


def main():
    print(
        "[test] Opening Arducam camera..."
    )

    camera = ArducamCamera(
        camera_index=1,
        width=5472,
        height=3648,
    )

    try:
        camera.open()

        print(
            "[test] Camera opened:",
            camera.is_open,
        )

        print(
            "[test] Requested resolution:",
            (
                camera.width,
                camera.height,
            ),
        )

        print(
            "[test] Camera-reported resolution:",
            camera.resolution,
        )

        print(
            "[test] Capturing frame..."
        )

        frame = camera.capture()

        height, width = frame.shape[:2]

        print(
            "[test] Captured frame resolution:",
            (
                width,
                height,
            ),
        )

        print(
            "[test] Shape:",
            frame.shape,
        )

        cv2.imshow(
            "Arducam Camera Test",
            frame,
        )

        print(
            "[test] Press any key "
            "in the image window to close."
        )

        cv2.waitKey(0)

    finally:
        camera.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()