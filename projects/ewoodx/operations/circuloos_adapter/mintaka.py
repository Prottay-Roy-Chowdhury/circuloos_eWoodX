"""Mintaka service client for the CIRCULOOS Data Platform."""

from .client import CirculoosClient


class MintakaClient:
    """Client for Mintaka temporal entity operations."""

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
            service="mintaka",
            method=method,
            endpoint=endpoint,
            tenant=tenant,
            context=context,
            **kwargs,
        )
