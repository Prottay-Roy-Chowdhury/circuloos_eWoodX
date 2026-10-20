"""Keycloak authentication for CIRCULOOS services."""

import os
import tempfile
import time
from pathlib import Path

import requests

from .config import (
    CirculoosConfig,
    ORION_TOKEN_FILE,
    MINTAKA_TOKEN_FILE,
)


class CirculoosAuth:
    """Manage Orion and Mintaka access tokens."""

    def __init__(self, config: CirculoosConfig):
        self.config = config
        self.session = requests.Session()
        self._tokens = {}

    def _client_credentials(self, service: str):
        clients = {
            "orion": (
                "orion-pep",
                self.config.orion_secret,
                ORION_TOKEN_FILE,
            ),
            "mintaka": (
                "mintaka-pep",
                self.config.mintaka_secret,
                MINTAKA_TOKEN_FILE,
            ),
        }

        if service not in clients:
            raise ValueError(
                f"Unknown CIRCULOOS service: {service}"
            )

        return clients[service]

    @staticmethod
    def _write_token(path: Path, token: str) -> None:
        """Atomically overwrite a token file."""

        path.parent.mkdir(parents=True, exist_ok=True)

        temporary_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_file.write(token)
                temporary_path = Path(temporary_file.name)

            os.replace(temporary_path, path)

        finally:
            if (
                temporary_path is not None
                and temporary_path.exists()
            ):
                temporary_path.unlink()

    def get_token(
        self,
        service: str,
        force_refresh: bool = False,
    ) -> str:

        client_id, client_secret, token_file = (
            self._client_credentials(service)
        )

        cached = self._tokens.get(service)

        if (
            not force_refresh
            and cached is not None
            and time.monotonic() < cached["expires_at"]
            and token_file.is_file()
        ):
            return cached["access_token"]

        response = self.session.post(
            self.config.token_url,
            data={
                "username": self.config.username,
                "password": self.config.password,
                "grant_type": "password",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=self.config.timeout,
        )

        response.raise_for_status()
        data = response.json()

        token = data.get("access_token")

        if not token:
            raise RuntimeError(
                f"No access token returned for {service}."
            )

        expires_in = float(
            data.get("expires_in", 60)
        )

        self._write_token(
            token_file,
            token,
        )

        self._tokens[service] = {
            "access_token": token,
            "expires_at": (
                time.monotonic()
                + max(0.0, expires_in - 30.0)
            ),
        }

        return token

    def invalidate(self, service: str) -> None:
        self._client_credentials(service)
        self._tokens.pop(service, None)

    def close(self) -> None:
        self.session.close()
