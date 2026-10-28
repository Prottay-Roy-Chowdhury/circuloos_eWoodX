"""ROS-independent two-sided Servo control agent.

GH TCP interface -> coordinator -> registered StreamClient
-> ServoMaster

Requires session-scoped ServoMaster protocol.
"""

import threading
import time
import uuid

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
    ):
        if update_hz <= 0 or arm_timeout <= 0:
            raise ValueError("Invalid timing configuration")

        self.period = 1.0 / update_hz
        self.arm_timeout = float(arm_timeout)

        self.gh = GrasshopperTCPInterface(
            host=gh_host,
            port=gh_port,
            input_timeout=input_timeout,
        )

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

        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._arm_event = threading.Event()

        self._arm_request_id = None
        self._arm_response = None

        self._master_armed = False
        self._master_session = None
        self._master_fault = False
        self._master_seq = 0
        self._active_gh_session = None

        # In-flight axis request IDs belonging to the
        # current master session.
        self._pending_axes = set()

        self._worker = None
        self._started = False

    @staticmethod
    def _request_id():
        return uuid.uuid4().hex

    def _on_master_message(self, message):
        if message.get("type") != "servo_ack":
            return

        request_id = message.get("request_id")
        request_type = message.get("request")

        with self._lock:
            # Only the matching arm acknowledgement can
            # satisfy the pending arm request.
            if (
                request_type == "servo_arm"
                and request_id == self._arm_request_id
            ):
                self._arm_response = message
                self._arm_event.set()
                return

            if (
                request_type == "servo_axes"
                and request_id in self._pending_axes
            ):
                self._pending_axes.discard(request_id)

                if (
                    self._master_armed
                    and not message.get("accepted", False)
                ):
                    self._master_fault = True
                return

            # Old, duplicate, or unrelated acknowledgements
            # cannot affect the current control session.

    def _on_master_disconnect(self):
        with self._lock:
            self._master_fault = True
            self._master_armed = False
            self._master_session = None
            self._pending_axes.clear()
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

    def _request_master_arm(self, gh_session):
        request_id = self._request_id()

        with self._lock:
            self._arm_request_id = request_id
            self._arm_response = None
            self._arm_event.clear()

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
                if response is not None
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
                # An arm request might be processed despite
                # an acknowledgement timeout. Send a stop.
                self._send_master_stop()
                return False

            with self._lock:
                self._master_armed = True
                self._master_session = master_session
                self._active_gh_session = gh_session
                self._master_seq = 0
                self._pending_axes.clear()

            print("[CONTROL] Master armed with new session")
            return True

        except (ConnectionError, OSError) as exc:
            print(f"[CONTROL] Master arm failed: {exc}")
            self._send_master_stop()
            return False

        finally:
            with self._lock:
                if self._arm_request_id == request_id:
                    self._arm_request_id = None

    def _send_axes(self, gh_state):
        request_id = self._request_id()

        with self._lock:
            if not self._master_armed:
                return

            session = self._master_session
            seq = self._master_seq
            self._master_seq += 1
            self._pending_axes.add(request_id)

        command = {
            "type": "servo_axes",
            "request_id": request_id,
            "session": session,
            "seq": seq,
            "linear": gh_state["linear"],
            "angular": gh_state["angular"],
        }

        try:
            self.client.send(command)
        except (ConnectionError, OSError):
            with self._lock:
                self._pending_axes.discard(request_id)
                self._master_fault = True

    def _run(self):
        next_tick = time.monotonic()

        while not self._stop_event.is_set():
            gh_state = self.gh.snapshot()

            with self._lock:
                fault = self._master_fault
                master_armed = self._master_armed
                active_gh = self._active_gh_session

            if fault or not self.client.registered:
                self._disarm_master(
                    "master connection/fault"
                )
                self._send_master_stop()
                self._invalidate_gh()
                self._stop_event.set()
                break

            if not gh_state["armed"]:
                self._disarm_master(gh_state["reason"])

            elif master_armed:
                if gh_state["session"] != active_gh:
                    self._disarm_master("GH session changed")
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

        self._disarm_master("control loop stopped")

    def start(self):
        if self._started:
            raise RuntimeError("Already started")

        self.client.connect()

        try:
            self.gh.start()
        except Exception:
            self.client.close()
            raise

        self._stop_event.clear()
        self._worker = threading.Thread(
            target=self._run,
            name="servo-control-coordinator",
            daemon=True,
        )
        self._worker.start()
        self._started = True

        print("[CONTROL] Master connected")
        print("[CONTROL] GH TCP interface started")

    def status(self):
        gh_state = self.gh.snapshot()

        with self._lock:
            return {
                "master_connected": self.client.registered,
                "master_armed": self._master_armed,
                "master_session": self._master_session,
                "master_fault": self._master_fault,
                "master_seq": self._master_seq,
                "gh": gh_state,
            }

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
        self._started = False

        print("[CONTROL] Stopped")


def main():
    control = ServoControlAgent()

    try:
        control.start()
        print("Press Ctrl+C to stop")

        while True:
            time.sleep(1.0)

            if control._stop_event.is_set():
                break

    except KeyboardInterrupt:
        pass

    finally:
        control.stop()


if __name__ == "__main__":
    main()