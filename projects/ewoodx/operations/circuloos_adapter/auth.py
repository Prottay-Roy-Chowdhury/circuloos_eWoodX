"""Keycloak authentication for CIRCULOOS services."""

import time
import requests

from .config import CirculoosConfig


class CirculoosAuth:
    """Manage independent Orion and Mintaka access tokens."""

    def __init__(self, config: CirculoosConfig):
        self.config = config
        self.session = requests.Session()
        self._tokens = {}

    def _client_credentials(self, service: str):
        clients = {
            "orion": (
                "orion-pep",
                self.config.orion_secret,
            ),
            "mintaka": (
                "mintaka-pep",
                self.config.mintaka_secret,
            ),
        }

        if service not in clients:
            raise ValueError(f"Unknown CIRCULOOS service: {service}")

        return clients[service]

    def get_token(self, service: str, force_refresh: bool = False) -> str:
        client_id, client_secret = self._client_credentials(service)

        cached = self._tokens.get(service)

        if (
            not force_refresh
            and cached is not None
            and time.monotonic() < cached["expires_at"]
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
                f"Keycloak did not return an access token for {service}."
            )

        expires_in = float(data.get("expires_in", 60))

        self._tokens[service] = {
            "access_token": token,
            "expires_at": (
                time.monotonic() + max(0.0, expires_in - 30.0)
            ),
        }

        return token

    def invalidate(self, service: str) -> None:
        self._client_credentials(service)
        self._tokens.pop(service, None)

    def close(self) -> None:
        self.session.close()
