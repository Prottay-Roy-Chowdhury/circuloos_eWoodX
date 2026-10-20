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


    # --------------------------------------------------
    # Retrieve temporal history of an entity
    # --------------------------------------------------

    def get_temporal_entity(
        self,
        entity_id: str,
        *,
        tenant: str,
        context: str | None = None,
        last_n: int = 10,
    ) -> dict:

        if not entity_id:
            raise ValueError("Entity ID cannot be empty.")

        if last_n < 1:
            raise ValueError("last_n must be positive.")

        encoded_id = self.client.encode_entity_id(
            entity_id
        )

        response = self.request(
            method="GET",
            endpoint=f"/temporal/entities/{encoded_id}",
            tenant=tenant,
            context=context,
            params={"lastN": last_n},
            accept="application/ld+json",
        )

        return response.json()
