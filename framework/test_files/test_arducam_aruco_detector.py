from pathlib import Path
import sys

import cv2
import numpy as np


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from framework.sensing import (
    ArducamArucoDetector,
)


def main():

    print(
        "[test] Creating synthetic ArUco image..."
    )

    dictionary = (
        cv2.aruco.getPredefinedDictionary(
            cv2.aruco.DICT_4X4_50
        )
    )

    canvas = np.full(
        (800, 1000),
        255,
        dtype=np.uint8,
    )

    marker_size = 150

    marker_positions = {
        0: (100, 100),
        1: (750, 100),
        2: (750, 550),
        3: (100, 550),
    }

    for marker_id, (
        x,
        y,
    ) in marker_positions.items():

        marker = (
            cv2.aruco.generateImageMarker(
                dictionary,
                marker_id,
                marker_size,
            )
        )

        canvas[
            y:y + marker_size,
            x:x + marker_size,
        ] = marker

    print(
        "[test] Detecting markers..."
    )

    detector = ArducamArucoDetector(
        dictionary_name="DICT_4X4_50",
    )

    detected = detector.detect(
        canvas
    )

    print(
        "[test] Detected marker IDs:"
    )
    print(
        sorted(detected.keys())
    )

    assert set(
        detected.keys()
    ) == {
        0,
        1,
        2,
        3,
    }

    for marker_id in sorted(
        detected.keys()
    ):

        corners = detected[
            marker_id
        ]

        print(
            f"[test] Marker {marker_id} corners:"
        )
        print(
            corners
        )

        assert corners.shape == (
            4,
            2,
        )

    print(
        "[test] Arducam ArUco "
        "detector test passed"
    )


if __name__ == "__main__":
    main()