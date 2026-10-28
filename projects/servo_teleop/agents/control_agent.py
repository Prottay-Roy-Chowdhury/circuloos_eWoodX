"""Two-sided ROS-independent Servo control agent.

Grasshopper TCP server :9061
Master-facing StreamClient :9060

"""

from pathlib import Path
import sys
from collections import OrderedDict
import threading
import time
import uuid

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from framework.communication.core import Agent
from framework.communication.workflow import StreamClient

from projects.servo_teleop.operations.grasshopper_tcp import (
    GrasshopperTCPInterface,
)


class ServoControlAgent:
    def __init__(
        self,
        master_host="127.0.0.1",
        master_port=9060,
        gh_host="127.0.0.1",
        gh_port=9061,
        update_hz=20.0,
        input_timeout=0.5,
        arm_timeout=2.0,
        ack_timeout=0.35,
        max_pending_axes=10,
    ):
        if update_hz <= 0 or arm_timeout <= 0:
            raise ValueError("Invalid timing configuration")

        if ack_timeout <= 0 or max_pending_axes < 1:
            raise ValueError("Invalid acknowledgement limits")

        self.period = 1.0 / float(update_hz)
        self.arm_timeout = float(arm_timeout)
        self.ack_timeout = float(ack_timeout)
        self.max_pending_axes = int(max_pending_axes)

        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._arm_event = threading.Event()

        self._phase = "STOPPED"
        self._reason = "not_started"
        self._master_fault = False

        self._arm_request_id = None
        self._arm_response = None

        self._master_armed = False
        self._master_session = None
        self._master_seq = 0
        self._active_gh_session = None

        # request_id -> (monotonic_send_time, master_session)
        self._pending_axes = OrderedDict()

        self._worker = None
        self._started = False

        self.client = StreamClient(
            agent=Agent(
                agent_id="servo_control_pc",
                roles=["servo_control"],
            ),
            host=master_host,
            port=master_port,
            on_message=self._on_master_message,
            on_disconnect=self._on_master_disconnect,
        )

        self.gh = GrasshopperTCPInterface(
            host=gh_host,
            port=gh_port,
            input_timeout=input_timeout,
            status_provider=self.control_status,
        )

    @staticmethod
    def _request_id():
        return uuid.uuid4().hex

    def control_status(self):
        """Thread-safe operational feedback for GH."""
        with self._lock:
            return {
                "state": self._phase,
                "reason": self._reason,
                "master_connected": self.client.registered,
                "master_armed": self._master_armed,
                "pending_axes": len(self._pending_axes),
            }

    def _set_phase(self, phase, reason):
        with self._lock:
            changed = (
                phase != self._phase
                or reason != self._reason
            )
            self._phase = phase
            self._reason = reason

        if changed:
            print(f"[CONTROL] {phase}: {reason}")

    def _fault(self, reason):
        with self._lock:
            if self._master_fault:
                return

            self._master_fault = True
            self._phase = "FAULT"
            self._reason = reason
            self._arm_event.set()

        print(f"[CONTROL] FAULT: {reason}")

    def _on_master_message(self, message):
        if message.get("type") != "servo_ack":
            return

        request_id = message.get("request_id")
        request_type = message.get("request")

        with self._lock:
            if (
                request_type == "servo_arm"
                and request_id == self._arm_request_id
            ):
                self._arm_response = message
                self._arm_event.set()
                return

            if request_type != "servo_axes":
                return

            pending = self._pending_axes.pop(
                request_id, None
            )

            if pending is None:
                # Old or unrelated acknowledgement.
                return

            _, expected_session = pending

            if not self._master_armed:
                return

            response_state = message.get("state", {})

            if (
                not message.get("accepted", False)
                or not isinstance(response_state, dict)
                or response_state.get("session")
                != expected_session
                or response_state.get("armed") is not True
            ):
                self._fault(
                    "master_axis_ack_rejected_or_invalid"
                )

    def _on_master_disconnect(self):
        with self._lock:
            if self._stop_event.is_set():
                return

        self._fault("master_tcp_disconnected")
        self._arm_event.set()

    def _invalidate_gh(self):
        state = self.gh.snapshot()

        if state["armed"]:
            self.gh.state.apply(
                state["owner"],
                {"type": "gh_stop"},
            )

    def _send_master_stop(self):
        if not self.client.registered:
            return

        try:
            self.client.send({
                "type": "servo_stop",
                "request_id": self._request_id(),
            })
        except (ConnectionError, OSError):
            pass

    def _disarm_master(self, reason):
        with self._lock:
            was_armed = self._master_armed
            self._master_armed = False
            self._master_session = None
            self._active_gh_session = None
            self._pending_axes.clear()

        if was_armed:
            self._send_master_stop()
            print(f"[CONTROL] Master disarmed: {reason}")

        with self._lock:
            faulted = self._master_fault

        if not faulted and not self._stop_event.is_set():
            self._set_phase("READY", reason)

    def _check_ack_watchdog(self):
        """Detect missing acknowledgements and backlog."""
        with self._lock:
            if not self._master_armed or self._master_fault:
                return

            if not self._pending_axes:
                return

            oldest_time, _ = next(
                iter(self._pending_axes.values())
            )

            age = time.monotonic() - oldest_time

            if age > self.ack_timeout:
                self._fault("master_axis_ack_timeout")

            elif len(self._pending_axes) >= self.max_pending_axes:
                self._fault("master_axis_ack_backlog")

    def _request_master_arm(self, gh_session):
        request_id = self._request_id()

        with self._lock:
            self._arm_request_id = request_id
            self._arm_response = None
            self._arm_event.clear()

        self._set_phase("ARMING", "awaiting_master_ack")

        try:
            self.client.send({
                "type": "servo_arm",
                "request_id": request_id,
            })

            acknowledged = self._arm_event.wait(
                self.arm_timeout
            )

            with self._lock:
                response = self._arm_response
                fault = self._master_fault

            state = (
                response.get("state", {})
                if isinstance(response, dict)
                else {}
            )

            current_gh = self.gh.snapshot()
            master_session = state.get("session")

            valid = (
                acknowledged
                and response is not None
                and response.get("accepted") is True
                and response.get("request") == "servo_arm"
                and response.get("request_id") == request_id
                and state.get("armed") is True
                and state.get("owner") == "servo_control_pc"
                and isinstance(master_session, str)
                and bool(master_session)
                and not fault
                and self.client.registered
                and current_gh["armed"]
                and current_gh["session"] == gh_session
                and current_gh["last_seq"] >= 0
            )

            if not valid:
                self._send_master_stop()

                if not fault:
                    self._set_phase(
                        "READY",
                        "master_arm_not_confirmed",
                    )

                return False

            with self._lock:
                self._master_armed = True
                self._master_session = master_session
                self._active_gh_session = gh_session
                self._master_seq = 0
                self._pending_axes.clear()

            self._set_phase("ACTIVE", "master_armed")
            return True

        except (ConnectionError, OSError) as exc:
            self._fault(f"master_arm_send_failed: {exc}")
            self._send_master_stop()
            return False

        finally:
            with self._lock:
                if self._arm_request_id == request_id:
                    self._arm_request_id = None

    def _send_axes(self, gh_state):
        self._check_ack_watchdog()

        with self._lock:
            if self._master_fault or not self._master_armed:
                return

            if len(self._pending_axes) >= self.max_pending_axes:
                self._fault("master_axis_ack_backlog")
                return

            request_id = self._request_id()
            session = self._master_session
            seq = self._master_seq
            self._master_seq += 1

            self._pending_axes[request_id] = (
                time.monotonic(),
                session,
            )

        try:
            self.client.send({
                "type": "servo_axes",
                "request_id": request_id,
                "session": session,
                "seq": seq,
                "linear": list(gh_state["linear"]),
                "angular": list(gh_state["angular"]),
            })

        except (ConnectionError, OSError) as exc:
            self._fault(f"master_axes_send_failed: {exc}")

    def _run(self):
        next_tick = time.monotonic()

        while not self._stop_event.is_set():
            gh_state = self.gh.snapshot()

            self._check_ack_watchdog()

            with self._lock:
                fault = self._master_fault
                armed = self._master_armed
                active_gh = self._active_gh_session

            if fault or not self.client.registered:
                if not fault:
                    self._fault("master_not_registered")

                self._disarm_master("master_fault")
                self._send_master_stop()
                self._invalidate_gh()
                self._stop_event.set()
                break

            if not gh_state["armed"]:
                if armed:
                    self._disarm_master(gh_state["reason"])

            elif armed:
                if gh_state["session"] != active_gh:
                    self._disarm_master(
                        "GH_session_changed"
                    )
                else:
                    self._send_axes(gh_state)

            elif gh_state["last_seq"] >= 0:
                session = gh_state["session"]

                if not self._request_master_arm(session):
                    self._invalidate_gh()

            next_tick += self.period
            remaining = next_tick - time.monotonic()

            if remaining < 0:
                next_tick = time.monotonic()
                remaining = 0

            self._stop_event.wait(remaining)

        self._disarm_master("coordinator_stopped")

    def start(self):
        if self._started:
            raise RuntimeError("Already started")

        # Faults are latched for the lifetime of this instance.
        with self._lock:
            if self._master_fault:
                raise RuntimeError(
                    "Faulted agent requires a fresh instance"
                )

        self.client.connect()

        try:
            self.gh.start()
        except Exception:
            self.client.close()
            raise

        self._stop_event.clear()
        self._started = True

        self._set_phase("READY", "operational")

        self._worker = threading.Thread(
            target=self._run,
            name="servo-control-coordinator",
            daemon=True,
        )
        self._worker.start()

    def status(self):
        result = self.control_status()

        with self._lock:
            result.update({
                "master_fault": self._master_fault,
                "master_session": self._master_session,
                "master_seq": self._master_seq,
                "pending_request_ids": list(
                    self._pending_axes.keys()
                ),
            })

        result["gh"] = self.gh.snapshot()
        return result

    def stop(self):
        self._stop_event.set()
        self._arm_event.set()

        if (
            self._worker is not None
            and self._worker is not threading.current_thread()
        ):
            self._worker.join(
                timeout=self.arm_timeout + 2.0
            )

        self._send_master_stop()
        self.gh.stop()
        self.client.close()

        with self._lock:
            self._master_armed = False
            self._master_session = None
            self._pending_axes.clear()
            self._started = False

        if not self._master_fault:
            self._set_phase("STOPPED", "service_stopped")

        print("[CONTROL] Stopped")


def main():
    control = ServoControlAgent()

    try:
        control.start()
        print("Press Ctrl+C to stop")

        while True:
            if control._stop_event.wait(1.0):
                break

    except KeyboardInterrupt:
        pass

    finally:
        control.stop()


if __name__ == "__main__":
    main()