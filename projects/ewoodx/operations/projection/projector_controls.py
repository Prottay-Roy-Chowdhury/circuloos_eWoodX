"""
eWoodX - Projector Controls

Keyboard and remote command controls for the eWoodX projector.

Responsibilities:
- Adjust timber thickness compensation.
- Nudge projection offsets.
- Adjust offset step size.
- Reset projection offsets.
- Toggle the projector HUD.
- Interpret remote projector commands.
- Request application lifecycle actions.

Does not handle:
- TCP communication or command responses
- Geometry processing
- OpenCV rendering
- JSON file monitoring
- Application lifecycle execution

Keyboard mappings and behavior are preserved from
the existing projector viewer.
"""

from __future__ import annotations

from projects.ewoodx.operations.projection.projector_state import (
    ProjectorState,
)

from projects.ewoodx.operations.projection.projector_renderer import (
    ProjectorRenderer,
)


class ProjectorControls:
    """
    Keyboard and remote controls for the modular projector.

    ProjectorState stores timber thickness.
    ProjectorRenderer stores offsets, step size and HUD state.

    Remote lifecycle commands return requested actions
    for the composer to execute.
    """

    STEP_SIZES = [
        0.1,
        0.25,
        0.5,
        1.0,
        2.0,
        5.0,
    ]

    def __init__(
        self,
        state: ProjectorState,
        renderer: ProjectorRenderer,
    ) -> None:

        self.state = state
        self.renderer = renderer

    # -------------------------------------------------------------
    # Thickness helpers
    # -------------------------------------------------------------

    def _get_thickness(self) -> float:
        """
        Read the current thickness from ProjectorState.
        """

        snapshot = self.state.get_snapshot()

        return float(snapshot[4])

    def _set_thickness(
        self,
        thickness_mm: float,
    ) -> None:

        thickness_mm = max(
            0.0,
            float(thickness_mm),
        )

        self.state.set_thickness(
            thickness_mm
        )

        print(
            "Thickness: "
            f"{thickness_mm:.1f} mm"
        )

    # -------------------------------------------------------------
    # Offset helpers
    # -------------------------------------------------------------

    def _nudge_x(
        self,
        direction: int,
    ) -> None:

        self.renderer.offset_x_mm += (
            direction * self.renderer.step_mm
        )

    def _nudge_y(
        self,
        direction: int,
    ) -> None:

        self.renderer.offset_y_mm += (
            direction * self.renderer.step_mm
        )

    def _change_step(
        self,
        direction: int,
    ) -> None:

        steps = self.STEP_SIZES

        current_step = (
            self.renderer.step_mm
        )

        if direction > 0:

            index = min(
                len(steps) - 1,
                (
                    steps.index(current_step) + 1
                    if current_step in steps
                    else 2
                ),
            )

        else:

            index = max(
                0,
                (
                    steps.index(current_step) - 1
                    if current_step in steps
                    else 2
                ),
            )

        self.renderer.step_mm = steps[index]

        print(
            "Nudge step: "
            f"{self.renderer.step_mm:.2f} mm"
        )

    # -------------------------------------------------------------
    # Main keyboard handler
    # -------------------------------------------------------------

    def handle_key(
        self,
        key: int,
    ) -> bool:
        """
        Process a key returned by cv2.waitKeyEx().

        Returns:
            True  - Continue projection.
            False - Exit projector application.

        Preserves the existing keyboard mappings.
        """

        # ---------------------------------------------------------
        # Exit
        # ---------------------------------------------------------

        if key in (
            27,
            ord("q"),
            ord("Q"),
        ):

            return False

        # ---------------------------------------------------------
        # Thickness
        # ---------------------------------------------------------

        if key == ord("t"):

            self._set_thickness(
                self._get_thickness() + 1.0
            )

        elif key == ord("T"):

            self._set_thickness(
                self._get_thickness() + 5.0
            )

        elif key == ord("g"):

            self._set_thickness(
                self._get_thickness() - 1.0
            )

        elif key == ord("G"):

            self._set_thickness(
                self._get_thickness() - 5.0
            )

        elif key == ord("0"):

            self.state.set_thickness(
                0.0
            )

            print(
                "Thickness reset to 0.0 mm "
                "(Table level)"
            )

        # ---------------------------------------------------------
        # Offset nudging
        # ---------------------------------------------------------

        elif key in (
            2490368,
            ord("w"),
            ord("W"),
        ):

            self._nudge_y(+1)

        elif key in (
            2621440,
            ord("s"),
            ord("S"),
        ):

            self._nudge_y(-1)

        elif key in (
            2555904,
            ord("d"),
            ord("D"),
        ):

            self._nudge_x(+1)

        elif key in (
            2424832,
            ord("a"),
            ord("A"),
        ):

            self._nudge_x(-1)

        # ---------------------------------------------------------
        # Step size
        # ---------------------------------------------------------

        elif key in (
            ord("+"),
            ord("="),
            ord("]"),
        ):

            self._change_step(+1)

        elif key in (
            ord("-"),
            ord("_"),
            ord("["),
        ):

            self._change_step(-1)

        # ---------------------------------------------------------
        # Reset offsets
        # ---------------------------------------------------------

        elif key in (
            ord("r"),
            ord("R"),
        ):

            self.renderer.offset_x_mm = 0.0
            self.renderer.offset_y_mm = 0.0

            print(
                "Offsets reset to "
                "X=0.0 mm, Y=0.0 mm"
            )

        # ---------------------------------------------------------
        # HUD
        # ---------------------------------------------------------

        elif key in (
            ord("h"),
            ord("H"),
        ):

            self.renderer.show_hud = (
                not self.renderer.show_hud
            )

        return True

    # -------------------------------------------------------------
    # Remote command interpretation
    # -------------------------------------------------------------

    def handle_command(
        self,
        command: str,
        parameters: dict | None = None,
        status: dict | None = None,
    ) -> dict:
        """
        Interpret a remote projector command.

        Returns:
            {
                "success": bool,
                "result": dict,
                "action": str | None,
            }

        The composer remains responsible for:
        - Executing lifecycle actions.
        - Collecting application-wide status.
        - Sending command responses.

        Supported commands:
        - get_status
        - set_thickness
        - pause
        - resume
        - stop
        - blank_projection
        - restore_projection

        This preserves the command set of the
        existing projector composer.
        """

        if parameters is None:
            parameters = {}

        if not isinstance(parameters, dict):

            return {
                "success": False,
                "result": {
                    "error": (
                        "Command parameters "
                        "must be a dictionary."
                    ),
                },
                "action": None,
            }

        try:

            # -----------------------------------------------------
            # Status
            # -----------------------------------------------------

            if command == "get_status":

                if status is None:
                    status = {}

                return {
                    "success": True,
                    "result": dict(status),
                    "action": None,
                }

            # -----------------------------------------------------
            # Thickness
            # -----------------------------------------------------

            elif command == "set_thickness":

                value = float(
                    parameters["thickness_mm"]
                )

                self.state.set_thickness(
                    value
                )

                return {
                    "success": True,
                    "result": {
                        "thickness_mm": value,
                    },
                    "action": None,
                }

            # -----------------------------------------------------
            # Pause
            # -----------------------------------------------------

            elif command == "pause":

                return {
                    "success": True,
                    "result": {
                        "paused": True,
                    },
                    "action": "pause",
                }

            # -----------------------------------------------------
            # Resume
            # -----------------------------------------------------

            elif command == "resume":

                return {
                    "success": True,
                    "result": {
                        "paused": False,
                    },
                    "action": "resume",
                }

            
            # -----------------------------------------------------
            # Blank projection
            # -----------------------------------------------------

            elif command == "blank_projection":

                session_id = parameters.get("session_id")

                if (
                    not isinstance(session_id, str)
                    or not session_id.strip()
                ):
                    raise ValueError(
                        "A valid session_id is required."
                    )

                return {
                    "success": True,
                    "result": {
                        "session_id": session_id,
                    },
                    "action": "blank_projection",
                }

            # -----------------------------------------------------
            # Restore projection
            # -----------------------------------------------------

            elif command == "restore_projection":

                session_id = parameters.get("session_id")

                if (
                    not isinstance(session_id, str)
                    or not session_id.strip()
                ):
                    raise ValueError(
                        "A valid session_id is required."
                    )

                return {
                    "success": True,
                    "result": {
                        "session_id": session_id,
                    },
                    "action": "restore_projection",
                }


            # -----------------------------------------------------
            # Stop
            # -----------------------------------------------------

            elif command == "stop":

                return {
                    "success": True,
                    "result": {
                        "stopping": True,
                    },
                    "action": "stop",
                }

            # -----------------------------------------------------
            # Unsupported command
            # -----------------------------------------------------

            else:

                return {
                    "success": False,
                    "result": {
                        "error": (
                            "Unsupported projector command: "
                            f"{command}"
                        ),
                    },
                    "action": None,
                }

        except (
            KeyError,
            TypeError,
            ValueError,
            OverflowError,
        ) as error:

            return {
                "success": False,
                "result": {
                    "error": str(error),
                },
                "action": None,
            }

    # -------------------------------------------------------------
    # Current control parameters
    # -------------------------------------------------------------

    def get_parameters(self) -> dict:
        """
        Return the current projector control parameters.
        """

        return {
            "thickness_mm": self._get_thickness(),
            "offset_x_mm": self.renderer.offset_x_mm,
            "offset_y_mm": self.renderer.offset_y_mm,
            "step_mm": self.renderer.step_mm,
            "show_hud": self.renderer.show_hud,
            "show_grid": self.renderer.show_grid,
        }