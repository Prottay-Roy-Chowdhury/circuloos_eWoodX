"""Authenticated HTTP client for the CIRCULOOS Data Platform."""

from typing import Any
from urllib.parse import quote

import requests

from .auth import CirculoosAuth
from .config import CirculoosConfig


class CirculoosHTTPError(RuntimeError):
    """A CIRCULOOS API request returned an unsuccessful status."""

    def __init__(self, response: requests.Response):
        self.status_code = response.status_code
        self.response_body = response.text

        super().__init__(
            f"CIRCULOOS HTTP {self.status_code}: "
            f"{self.response_body[:500]}"
        )


class CirculoosClient:
    """Shared transport for Orion-LD and Mintaka requests."""

    def __init__(
        self,
        config: CirculoosConfig,
        auth: CirculoosAuth | None = None,
    ):
        self.config = config
        self.auth = auth or CirculoosAuth(config)
        self._owns_auth = auth is None
        self.session = requests.Session()

    def _base_url(self, service: str) -> str:
        if service == "orion":
            return self.config.orion_url

        if service == "mintaka":
            return self.config.mintaka_url

        raise ValueError(f"Unknown CIRCULOOS service: {service}")

    def _headers(
        self,
        service: str,
        token: str,
        tenant: str,
        accept: str,
        content_type: str | None,
        context: str | None,
    ) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {token}",
            "NGSILD-Tenant": tenant,
            "Accept": accept,
        }

        if service == "orion":
            headers["NGSILD-Path"] = "/"

        if content_type:
            headers["Content-Type"] = content_type

        if context:
            headers["Link"] = (
                f'<{context}>; '
                'rel="http://www.w3.org/ns/json-ld#context"; '
                'type="application/ld+json"'
            )

        return headers

    def request(
        self,
        service: str,
        method: str,
        endpoint: str,
        *,
        tenant: str,
        context: str | None = None,
        params: dict[str, Any] | None = None,
        json_data: Any = None,
        accept: str = "application/json",
        content_type: str | None = None,
    ) -> requests.Response:
        """Send an authenticated request and return its raw response."""

        base_url = self._base_url(service)

        if not endpoint.startswith("/") or endpoint.startswith("//"):
            raise ValueError("Endpoint must start with a single '/'.")

        if "://" in endpoint or "#" in endpoint:
            raise ValueError("Invalid endpoint.")

        if not isinstance(tenant, str) or not tenant.strip():
            raise ValueError("Tenant must be a non-empty string.")

        url = base_url + endpoint
        method = method.upper()

        if method not in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
            raise ValueError(f"Unsupported HTTP method: {method}")

        if json_data is not None and content_type is None:
            content_type = "application/json"

        for attempt in range(2):
            token = self.auth.get_token(
                service,
                force_refresh=(attempt == 1),
            )

            response = self.session.request(
                method=method,
                url=url,
                headers=self._headers(
                    service,
                    token,
                    tenant,
                    accept,
                    content_type,
                    context,
                ),
                params=params,
                json=json_data,
                timeout=self.config.timeout,
            )

            # Retry once with a new token if authorization expired.
            if response.status_code == 401 and attempt == 0:
                response.close()
                self.auth.invalidate(service)
                continue

            if not response.ok:
                raise CirculoosHTTPError(response)

            return response

        raise RuntimeError("Authentication retry failed.")

    @staticmethod
    def encode_entity_id(entity_id: str) -> str:
        """Safely encode an NGSI-LD entity ID for a URL path."""
        return quote(entity_id, safe="")

    def close(self) -> None:
        self.session.close()

        if self._owns_auth:
            self.auth.close()
