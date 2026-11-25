"""
Common utilities for eWoodX streaming services.

Built on the generic framework StreamClient.

No camera, projector, or persistence logic.
"""

import copy
import json
import queue
import threading
import time
import uuid

from typing import Callable

from framework.communication.core import Agent
from framework.communication.workflow.stream_client import (
    StreamClient,
)


# ---------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------

MEASUREMENT = "ewoodx.measurement"
PROJECTOR = "ewoodx.projector"
STATUS = "ewoodx.status"

COMMAND = "ewoodx.command"
COMMAND_RESULT = "ewoodx.command_result"

SUBSCRIBE = "ewoodx.subscribe"
UNSUBSCRIBE = "ewoodx.unsubscribe"

STREAM_TOPICS = {
    MEASUREMENT,
    PROJECTOR,
    STATUS,
}

CONTROL_COMMANDS = {
    "save",
    "set_thickness",
    "stop",
    "pause",
    "resume",
    "get_status",
    "blank_projection",
    "restore_projection",
}


# ---------------------------------------------------------------------
# Message helpers
# ---------------------------------------------------------------------

def json_copy(value):
    """Validate JSON compatibility and detach mutable data."""
    return json.loads(
        json.dumps(value, allow_nan=False)
    )


def make_message(message_type, **fields):
    return {
        "type": message_type,
        "timestamp": time.time(),
        **fields,
    }


def new_request_id():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------
# Latest-value buffer
# ---------------------------------------------------------------------

class LatestValue:
    """
    Thread-safe latest-value storage.

    A newer value replaces the previous one.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._value = None
        self._revision = 0

    def update(self, value):
        with self._lock:
            self._value = copy.deepcopy(value)
            self._revision += 1
            return self._revision

    def get(self):
        with self._lock:
            return (
                self._revision,
                copy.deepcopy(self._value),
            )


# ---------------------------------------------------------------------
# Shared endpoint
# ---------------------------------------------------------------------

class StreamEndpointBase:
    """
    Shared registered endpoint for agent-specific services.

    Supports:
    - Persistent registered connection
    - Topic subscriptions
    - Latest-value outgoing stream buffers
    - FIFO command/result queues
    - Background streaming sender
    - Explicit connection lifecycle

    Control messages are sent synchronously.
    """

    def __init__(
        self,
        agent_id: str,
        roles: list[str],
        host: str,
        port: int,
        stream_topics=None,
        command_queue_size=128,
        on_stream: Callable | None = None,
    ):
        self.agent_id = agent_id
        self.roles = list(roles)

        self.agent = Agent(
            agent_id=agent_id,
            roles=self.roles,
        )

        self._on_stream_callback = on_stream

        topics = set(stream_topics or [])

        unknown = topics - STREAM_TOPICS
        if unknown:
            raise ValueError(
                f"Unsupported stream topics: {unknown}"
            )

        self._outgoing = {
            topic: LatestValue()
            for topic in topics
        }

        self._latest = {
            topic: LatestValue()
            for topic in STREAM_TOPICS
        }

        self.commands = queue.Queue(
            maxsize=command_queue_size
        )
        self.results = queue.Queue()

        self._send_lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._sender_thread = None

        self._client = StreamClient(
            agent=self.agent,
            host=host,
            port=port,
            on_message=self._handle_message,
            on_disconnect=self._handle_disconnect,
        )

    @property
    def connected(self):
        return self._client.registered

    def start(self, subscribe=None):
        if self._sender_thread is not None:
            if self._sender_thread.is_alive():
                raise RuntimeError(
                    "Stream endpoint already running."
                )

        self._client.connect()

        try:
            self._stop.clear()
            self._wake.clear()

            if subscribe:
                self._send(
                    make_message(
                        SUBSCRIBE,
                        topics=list(subscribe),
                    )
                )

            self._sender_thread = threading.Thread(
                target=self._sender_loop,
                name=f"{self.agent_id}-stream",
                daemon=True,
            )
            self._sender_thread.start()

        except Exception:
            self._client.close()
            raise

    def stop(self):
        self._stop.set()
        self._wake.set()

        thread = self._sender_thread

        # Closing the connection first releases blocked I/O.
        self._client.close()

        if (
            thread is not None
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=2.0)

        self._sender_thread = None

    def _send(self, message):
        with self._send_lock:
            self._client.send(message)

    def subscribe(self, topics):
        self._send(
            make_message(
                SUBSCRIBE,
                topics=list(topics),
            )
        )

    def unsubscribe(self, topics):
        self._send(
            make_message(
                UNSUBSCRIBE,
                topics=list(topics),
            )
        )

    def publish_latest(self, topic, payload, **fields):
        """
        Non-blocking publication from the caller's perspective.

        The sender thread transmits the latest available
        message for this topic.
        """
        if topic not in self._outgoing:
            raise ValueError(
                f"Topic not configured for publication: {topic}"
            )

        message = make_message(
            topic,
            payload=json_copy(payload),
            **fields,
        )

        self._outgoing[topic].update(message)
        self._wake.set()

    def publish_status(self, status):
        self._send(
            make_message(
                STATUS,
                payload=json_copy(status),
            )
        )

    def send_command(
        self,
        target,
        command,
        parameters=None,
        request_id=None,
    ):
        if command not in CONTROL_COMMANDS:
            raise ValueError(
                f"Unsupported command: {command}"
            )

        request_id = request_id or new_request_id()

        self._send(
            make_message(
                COMMAND,
                target=target,
                request_id=request_id,
                command=command,
                parameters=json_copy(
                    parameters or {}
                ),
            )
        )

        return request_id

    def send_command_result(
        self,
        target,
        request_id,
        success,
        result=None,
    ):
        self._send(
            make_message(
                COMMAND_RESULT,
                target=target,
                request_id=request_id,
                success=bool(success),
                result=json_copy(
                    result if result is not None else {}
                ),
            )
        )

    def get_command(self, timeout=None):
        try:
            return self.commands.get(
                timeout=timeout if timeout is not None else 0
            )
        except queue.Empty:
            return None

    def get_result(self, timeout=None):
        try:
            return self.results.get(
                timeout=timeout if timeout is not None else 0
            )
        except queue.Empty:
            return None

    def get_latest(self, topic):
        if topic not in self._latest:
            raise ValueError(
                f"Unsupported topic: {topic}"
            )
        return self._latest[topic].get()

    def _sender_loop(self):
        last_revisions = {
            topic: 0
            for topic in self._outgoing
        }

        while not self._stop.is_set():
            self._wake.wait(timeout=0.2)
            self._wake.clear()

            if self._stop.is_set():
                break

            for topic, buffer in self._outgoing.items():
                revision, message = buffer.get()

                if (
                    message is None
                    or revision == last_revisions[topic]
                ):
                    continue

                try:
                    self._send(message)
                    last_revisions[topic] = revision

                except (ConnectionError, OSError):
                    self._stop.set()
                    return

    def _handle_message(self, message):
        message_type = message.get("type")

        if message_type in STREAM_TOPICS:
            self._latest[message_type].update(message)

            if self._on_stream_callback is not None:
                try:
                    self._on_stream_callback(message)
                except Exception as error:
                    print(
                        "[eWoodX stream] Callback error:",
                        error,
                    )
            return

        if message_type == COMMAND:
            if message.get("target") != self.agent_id:
                return

            try:
                self.commands.put_nowait(message)

            except queue.Full:
                try:
                    self.send_command_result(
                        target=message.get("source"),
                        request_id=message.get("request_id"),
                        success=False,
                        result={
                            "error": "Command queue is full."
                        },
                    )
                except (ConnectionError, OSError):
                    pass
            return

        if message_type == COMMAND_RESULT:
            if message.get("target") == self.agent_id:
                self.results.put(message)

    def _handle_disconnect(self):
        self._stop.set()
        self._wake.set()