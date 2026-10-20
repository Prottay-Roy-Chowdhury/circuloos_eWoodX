"""Orion-LD service client for the CIRCULOOS Data Platform."""

from .client import CirculoosClient


class OrionClient:
    """Client for Orion-LD entity operations."""

    def __init__(
        self,
        client: CirculoosClient,
    ):
        self.client = client

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        tenant: str,
        context: str | None = None,
        **kwargs,
    ):
        return self.client.request(
            service="orion",
            method=method,
            endpoint=endpoint,
            tenant=tenant,
            context=context,
            **kwargs,
        )
