
"""Continuous ROSBridge WebSocket performance and recovery test.

Runs entirely on Windows without ROS or Docker.
Measures:
    - Publishing frequency and interval jitter
    - Echo reception frequency
    - Local WebSocket round-trip latency
    - Missing, duplicate, and out-of-order messages
    - Recovery after an unexpected WebSocket disconnect

This is a communication benchmark, not a robot safety test.
"""

import json
import math
import statistics
import sys
import threading
import time
from pathlib import Path

from websockets.sync.server import serve

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from framework.communication.transport.rosbridge import ROSBridgeClient


HOST = "127.0.0.1"
TOPIC = "/test_rosbridge_stream"
MSG_TYPE = "std_msgs/String"

RATES = [20, 50, 100]
DURATION_SEC = 5.0

CONNECT_TIMEOUT = 5.0
RECONNECT_TIMEOUT = 20.0
RECEIVE_TIMEOUT = 5.0


def wait_until(predicate, timeout=5.0):
    deadline = time.perf_counter() + timeout

    while time.perf_counter() < deadline:
        if predicate():
            return True
        time.sleep(0.01)

    return bool(predicate())


def percentile(values, percentage):
    """Linear-interpolated percentile."""
    if not values:
        return math.nan

    ordered = sorted(values)
    position = (len(ordered) - 1) * percentage / 100.0

    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return ordered[lower]

    fraction = position - lower
    return (
        ordered[lower] * (1.0 - fraction)
        + ordered[upper] * fraction
    )


class LocalBridgeServer:
    """Small ROSBridge-like WebSocket echo server."""

    def __init__(self):
        self.lock = threading.RLock()
        self.server = None
        self.thread = None
        self.port = None

        self.next_id = 0
        self.connections = {}
        self.session_ops = {}

    def start(self):
        self.server = serve(self.handle, HOST, 0)
        self.port = self.server.socket.getsockname()[1]

        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()

        print(f"[SERVER] ws://{HOST}:{self.port}")

    def handle(self, websocket):
        with self.lock:
            self.next_id += 1
            session_id = self.next_id
            self.connections[session_id] = websocket
            self.session_ops[session_id] = set()

        subscriptions = set()

        print(f"[SERVER] Connected session {session_id}")

        try:
            for raw in websocket:
                message = json.loads(raw)

                op = message.get("op")
                topic = message.get("topic")

                if op in {"subscribe", "advertise"}:
                    with self.lock:
                        self.session_ops[session_id].add(
                            (op, topic)
                        )

                if op == "subscribe":
                    subscriptions.add(topic)

                elif op == "unsubscribe":
                    subscriptions.discard(topic)

                elif op == "publish":
                    if topic in subscriptions:
                        websocket.send(json.dumps({
                            "op": "publish",
                            "topic": topic,
                            "msg": message.get("msg", {}),
                        }))

        except Exception as exc:
            print(
                f"[SERVER] Session {session_id} ended: {exc}"
            )

        finally:
            with self.lock:
                self.connections.pop(session_id, None)

            print(f"[SERVER] Disconnected session {session_id}")

    def current_session(self):
        with self.lock:
            return self.next_id

    def has_op(self, session_id, op, topic=TOPIC):
        with self.lock:
            return (
                (op, topic)
                in self.session_ops.get(session_id, set())
            )

    def disconnect_all(self):
        with self.lock:
            sockets = list(self.connections.values())

        for websocket in sockets:
            websocket.close(
                code=1012,
                reason="Performance test disconnect",
            )

    def stop(self):
        if self.server is not None:
            self.server.shutdown()

        if self.thread is not None:
            self.thread.join(timeout=5)

        print("[SERVER] Stopped")


class Recorder:
    """Thread-safe echo callback and per-run measurements."""

    def __init__(self):
        self.lock = threading.Lock()
        self.received = {}

    def callback(self, msg):
        received_ns = time.perf_counter_ns()

        try:
            payload = json.loads(msg["data"])
            run_id = payload["run"]
            seq = int(payload["seq"])
            sent_ns = int(payload["sent_ns"])

        except (KeyError, TypeError, ValueError) as exc:
            print(f"[WARNING] Invalid echo: {exc}")
            return

        with self.lock:
            self.received.setdefault(run_id, []).append(
                (seq, sent_ns, received_ns)
            )

    def get(self, run_id):
        with self.lock:
            return list(self.received.get(run_id, []))

    def count(self, run_id):
        with self.lock:
            return len(self.received.get(run_id, []))


def measure_run(client, recorder, hz, duration, run_id):
    """Publish at an absolute monotonic-clock schedule."""

    period = 1.0 / hz
    count = round(hz * duration)

    sent = []
    errors = []

    start = time.perf_counter()

    for seq in range(count):
        deadline = start + seq * period

        remaining = deadline - time.perf_counter()
        if remaining > 0:
            time.sleep(remaining)

        sent_ns = time.perf_counter_ns()

        payload = {
            "run": run_id,
            "seq": seq,
            "sent_ns": sent_ns,
        }

        try:
            client.publish(
                topic=TOPIC,
                msg_type=MSG_TYPE,
                message={
                    "data": json.dumps(payload)
                },
            )

            sent.append((seq, sent_ns))

        except Exception as exc:
            errors.append((seq, str(exc)))

    # Wait for echoes without using an arbitrary fixed sleep.
    wait_until(
        lambda: recorder.count(run_id) >= len(sent),
        timeout=RECEIVE_TIMEOUT,
    )

    received = recorder.get(run_id)

    return {
        "run": run_id,
        "hz": hz,
        "duration": duration,
        "attempted": count,
        "sent": sent,
        "received": received,
        "errors": errors,
    }


def summarize(result):
    hz = result["hz"]
    sent = result["sent"]
    received = result["received"]
    errors = result["errors"]

    sent_times = [
        timestamp for _, timestamp in sent
    ]

    recv_times = [
        timestamp for _, _, timestamp in received
    ]

    sent_intervals = [
        (b - a) / 1e6
        for a, b in zip(sent_times, sent_times[1:])
    ]

    recv_intervals = [
        (b - a) / 1e6
        for a, b in zip(recv_times, recv_times[1:])
    ]

    rtt_ms = [
        (received_ns - sent_ns) / 1e6
        for _, sent_ns, received_ns in received
    ]

    sent_sequences = {
        seq for seq, _ in sent
    }

    received_sequences = [
        seq for seq, _, _ in received
    ]

    unique_received = set(received_sequences)

    missing = sent_sequences - unique_received
    duplicates = len(received_sequences) - len(unique_received)

    out_of_order = sum(
        current < previous
        for previous, current in zip(
            received_sequences,
            received_sequences[1:],
        )
    )

    def effective_rate(timestamps):
        if len(timestamps) < 2:
            return 0.0

        elapsed = (
            timestamps[-1] - timestamps[0]
        ) / 1e9

        return (
            (len(timestamps) - 1) / elapsed
            if elapsed > 0
            else 0.0
        )

    target_interval = 1000.0 / hz

    interval_errors = [
        interval - target_interval
        for interval in sent_intervals
    ]

    print()
    print("=" * 54)
    print(f"RUN: {result['run']} | TARGET: {hz} Hz")
    print("=" * 54)

    print(f"Attempted messages:    {result['attempted']}")
    print(f"Publish calls returned:{len(sent):>6}")
    print(f"Echoes received:       {len(received):>6}")
    print(f"Publish errors:        {len(errors):>6}")
    print(f"Missing sequences:     {len(missing):>6}")
    print(f"Duplicate sequences:   {duplicates:>6}")
    print(f"Out-of-order pairs:    {out_of_order:>6}")

    print()
    print(f"Publish rate: {effective_rate(sent_times):.2f} Hz")
    print(f"Receive rate: {effective_rate(recv_times):.2f} Hz")

    if sent_intervals:
        print()
        print("Publish interval")
        print(f"  Target:   {target_interval:.3f} ms")
        print(
            f"  Mean:     "
            f"{statistics.mean(sent_intervals):.3f} ms"
        )
        print(
            f"  Std dev:  "
            f"{statistics.pstdev(sent_intervals):.3f} ms"
        )
        print(
            f"  Minimum:  {min(sent_intervals):.3f} ms"
        )
        print(
            f"  Maximum:  {max(sent_intervals):.3f} ms"
        )
        print(
            f"  P95 |jitter|: "
            f"{percentile([abs(e) for e in interval_errors], 95):.3f} ms"
        )

    if recv_intervals:
        print()
        print("Receive interval")
        print(
            f"  Mean:     "
            f"{statistics.mean(recv_intervals):.3f} ms"
        )
        print(
            f"  Std dev:  "
            f"{statistics.pstdev(recv_intervals):.3f} ms"
        )
        print(
            f"  Maximum:  {max(recv_intervals):.3f} ms"
        )

    if rtt_ms:
        print()
        print("Local WebSocket round-trip latency")
        print(f"  Mean: {statistics.mean(rtt_ms):.3f} ms")
        print(f"  P50:  {percentile(rtt_ms, 50):.3f} ms")
        print(f"  P95:  {percentile(rtt_ms, 95):.3f} ms")
        print(f"  P99:  {percentile(rtt_ms, 99):.3f} ms")
        print(f"  Max:  {max(rtt_ms):.3f} ms")

    if errors:
        print()
        print("First publish errors:")
        for seq, error in errors[:5]:
            print(f"  seq={seq}: {error}")

    complete = (
        not errors
        and len(sent) == result["attempted"]
        and len(missing) == 0
        and duplicates == 0
        and out_of_order == 0
    )

    print()
    print(
        "Delivery integrity: "
        + ("PASS" if complete else "FAIL")
    )

    return complete


def main():
    server = LocalBridgeServer()
    client = None
    recorder = Recorder()

    all_passed = True

    try:
        server.start()

        client = ROSBridgeClient(
            host=HOST,
            port=server.port,
            timeout=CONNECT_TIMEOUT,
        )

        print("\n[1] Connecting")
        client.connect()

        assert client.connected

        print("[PASS] Connected")

        client.subscribe(
            TOPIC,
            MSG_TYPE,
            recorder.callback,
        )

        # Advertise before starting performance measurement.
        client.advertise(TOPIC, MSG_TYPE)

        session_id = server.current_session()

        assert wait_until(
            lambda: (
                server.has_op(session_id, "subscribe")
                and server.has_op(session_id, "advertise")
            )
        ), "Topic setup not received by server"

        print("[PASS] Subscription and advertisement ready")

        # --------------------------------------------------
        # Baseline streaming
        # --------------------------------------------------

        for hz in RATES:
            print(f"\n[2] Streaming at {hz} Hz")

            result = measure_run(
                client=client,
                recorder=recorder,
                hz=hz,
                duration=DURATION_SEC,
                run_id=f"baseline_{hz}",
            )

            passed = summarize(result)
            all_passed = all_passed and passed

            # Separate runs and let callbacks settle.
            time.sleep(0.3)

        # --------------------------------------------------
        # Recovery test
        # --------------------------------------------------

        print()
        print("=" * 54)
        print("CONNECTION RECOVERY TEST")
        print("=" * 54)

        previous_session = server.current_session()

        server.disconnect_all()

        assert wait_until(
            lambda: not client.connected,
            timeout=CONNECT_TIMEOUT,
        ), "Disconnect not detected"

        print("[PASS] Connection loss detected")

        # No publishing while disconnected.
        try:
            client.publish(
                TOPIC,
                MSG_TYPE,
                {"data": "should_not_publish"},
            )
        except ConnectionError:
            print("[PASS] Disconnected publish rejected")
        else:
            raise AssertionError(
                "Publish accepted during disconnection"
            )

        assert wait_until(
            lambda: (
                client.connected
                and server.current_session() > previous_session
            ),
            timeout=RECONNECT_TIMEOUT,
        ), "Automatic reconnection failed"

        new_session = server.current_session()

        print("[PASS] Connection restored")

        assert wait_until(
            lambda: (
                server.has_op(new_session, "subscribe")
                and server.has_op(new_session, "advertise")
            ),
            timeout=CONNECT_TIMEOUT,
        ), "Topic registrations not restored"

        print("[PASS] Topic registrations restored")

        # New, explicitly initiated session.
        # Do not replay old commands after reconnecting.
        result = measure_run(
            client=client,
            recorder=recorder,
            hz=50,
            duration=3.0,
            run_id="after_reconnect_50",
        )

        passed = summarize(result)
        all_passed = all_passed and passed

        print()
        print("=" * 54)
        print(
            "STREAM PERFORMANCE TEST: "
            + ("PASS" if all_passed else "CHECK RESULTS")
        )
        print("=" * 54)

    finally:
        if client is not None:
            client.close()

        server.stop()


if __name__ == "__main__":
    main()