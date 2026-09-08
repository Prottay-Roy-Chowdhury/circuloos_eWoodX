import cv2
import numpy as np


class ArducamArucoDetector:
    """
    Detect ArUco markers in an image.

    The detector returns marker corners indexed by marker ID.
    Marker layout and physical-world correspondence are
    intentionally left to the project layer.
    """

    def __init__(
        self,
        dictionary_name: str,
    ) -> None:

        if not isinstance(
            dictionary_name,
            str,
        ):
            raise TypeError(
                "dictionary_name must be a string."
            )

        if not hasattr(
            cv2.aruco,
            dictionary_name,
        ):
            raise ValueError(
                f"Unknown ArUco dictionary: "
                f"{dictionary_name}"
            )

        dictionary_id = getattr(
            cv2.aruco,
            dictionary_name,
        )

        self.dictionary_name = (
            dictionary_name
        )

        self.dictionary = (
            cv2.aruco.getPredefinedDictionary(
                dictionary_id
            )
        )

        self.parameters = (
            cv2.aruco.DetectorParameters()
        )

        self.detector = (
            cv2.aruco.ArucoDetector(
                self.dictionary,
                self.parameters,
            )
        )

    def detect(
        self,
        image,
    ):

        if image is None:
            raise ValueError(
                "image cannot be None."
            )

        image = np.asarray(
            image
        )

        if image.ndim == 3:

            gray = cv2.cvtColor(
                image,
                cv2.COLOR_BGR2GRAY,
            )

        elif image.ndim == 2:

            gray = image

        else:
            raise ValueError(
                "image must be a grayscale "
                "or BGR image."
            )

        corners, ids, _ = (
            self.detector.detectMarkers(
                gray
            )
        )

        if ids is None:
            return {}

        ids = ids.flatten()

        detected = {}

        for marker_id, marker_corners in zip(
            ids,
            corners,
        ):

            detected[
                int(marker_id)
            ] = np.asarray(
                marker_corners[0],
                dtype=np.float32,
            )

        return detected