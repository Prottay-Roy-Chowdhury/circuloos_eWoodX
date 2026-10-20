"""Orion-LD service client for the CIRCULOOS Data Platform."""

from typing import Any

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

    # --------------------------------------------------
    # Retrieve a single entity
    # --------------------------------------------------

    def get_entity(
        self,
        entity_id: str,
        *,
        tenant: str,
        context: str | None = None,
    ) -> dict[str, Any]:

        if not entity_id:
            raise ValueError("Entity ID cannot be empty.")

        encoded_id = self.client.encode_entity_id(
            entity_id
        )

        response = self.request(
            method="GET",
            endpoint=f"/ngsi-ld/v1/entities/{encoded_id}",
            tenant=tenant,
            context=context,
            accept="application/ld+json",
        )

        return response.json()


    # --------------------------------------------------
    # Retrieve entities with type or ID pattern filtering
    # --------------------------------------------------

    def get_entities(
        self,
        *,
        tenant: str,
        entity_type: str | None = None,
        id_pattern: str | None = None,
        context: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:

        if limit < 1:
            raise ValueError("Limit must be positive.")

        if offset < 0:
            raise ValueError("Offset cannot be negative.")

        params = {
            "limit": limit,
            "offset": offset,
        }

        if entity_type:
            params["type"] = entity_type

        if id_pattern:
            params["idPattern"] = id_pattern

        # Orion-LD requires a query constraint.
        # Match the official CIRCULOOS ID listing behavior
        # when no other filter is provided.
        if not entity_type and not id_pattern:
            params["idPattern"] = "urn:ngsi-ld:.*"

        response = self.request(
            method="GET",
            endpoint="/ngsi-ld/v1/entities",
            tenant=tenant,
            context=context,
            params=params,
            accept="application/ld+json",
        )

        return response.json()

    # --------------------------------------------------
    # Retrieve entity IDs
    # --------------------------------------------------

    def get_entity_ids(
        self,
        *,
        tenant: str,
        id_pattern: str = "urn:ngsi-ld:.*",
        limit: int = 1000,
        offset: int = 0,
    ) -> list[str]:

        if limit < 1:
            raise ValueError("Limit must be positive.")

        if offset < 0:
            raise ValueError("Offset cannot be negative.")

        response = self.request(
            method="GET",
            endpoint="/ngsi-ld/v1/entities",
            tenant=tenant,
            params={
                "idPattern": id_pattern,
                "limit": limit,
                "offset": offset,
            },
            accept="application/json",
            content_type="application/ld+json",
        )

        entities = response.json()

        return [
            entity["id"]
            for entity in entities
        ]
    
    # --------------------------------------------------
    # Create or update entities
    # --------------------------------------------------

    def upsert_entities(
        self,
        entities: list[dict],
        *,
        tenant: str,
        context: str | None = None,
    ) -> None:
        """Create or update NGSI-LD entities through Orion-LD."""

        if not isinstance(entities, list) or not entities:
            raise ValueError(
                "Entities must be a non-empty list."
            )

        for entity in entities:
            if not isinstance(entity, dict):
                raise ValueError(
                    "Each entity must be a dictionary."
                )

            if not entity.get("id") or not entity.get("type"):
                raise ValueError(
                    "Each entity must contain an ID and type."
                )

        self.request(
            method="POST",
            endpoint="/ngsi-ld/v1/entityOperations/upsert",
            tenant=tenant,
            context=context,
            json_data=entities,
            accept="application/json",
            content_type="application/json",
        )

    # --------------------------------------------------
    # Delete entity
    # --------------------------------------------------

    def delete_entity(
        self,
        entity_id: str,
        *,
        tenant: str,
        context: str | None = None,
    ) -> None:
        """Delete an NGSI-LD entity from Orion-LD."""

        if not entity_id:
            raise ValueError("entity_id must not be empty")

        encoded_id = self.client.encode_entity_id(entity_id)

        self.request(
            method="DELETE",
            endpoint=f"/ngsi-ld/v1/entities/{encoded_id}",
            tenant=tenant,
            context=context,
        )