"""Test CIRCULOOS Orion and Mintaka client initialization and routing."""

from pathlib import Path
import sys
from unittest.mock import patch


PROJECT_ROOT = Path(
    __file__
).resolve().parents[5]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from projects.ewoodx.operations.circuloos_adapter import (
    CirculoosConfig,
    CirculoosClient,
    OrionClient,
    MintakaClient,
)


def main() -> None:

    print()
    print("[CIRCULOOS] Service Clients Test")
    print("-" * 40)

    # --------------------------------------------------
    # Configuration and shared client
    # --------------------------------------------------

    config = CirculoosConfig.from_partner_file()

    client = CirculoosClient(
        config=config,
    )

    try:

        # --------------------------------------------------
        # Initialize service clients
        # --------------------------------------------------

        orion = OrionClient(
            client=client,
        )

        mintaka = MintakaClient(
            client=client,
        )

        assert orion.client is client
        assert mintaka.client is client

        print("OrionClient initialization: SUCCESS")
        print("MintakaClient initialization: SUCCESS")
        print("Shared HTTP client: SUCCESS")

        # --------------------------------------------------
        # Test Orion request routing
        # --------------------------------------------------

        with patch.object(client, "request") as mock_request:

            orion.request(
                method="GET",
                endpoint="/ngsi-ld/v1/entities",
                tenant="test_tenant",
            )

            mock_request.assert_called_once_with(
                service="orion",
                method="GET",
                endpoint="/ngsi-ld/v1/entities",
                tenant="test_tenant",
                context=None,
            )

        print("Orion request routing: SUCCESS")

        # --------------------------------------------------
        # Test Mintaka request routing
        # --------------------------------------------------

        with patch.object(client, "request") as mock_request:

            mintaka.request(
                method="GET",
                endpoint="/temporal/entities",
                tenant="test_tenant",
            )

            mock_request.assert_called_once_with(
                service="mintaka",
                method="GET",
                endpoint="/temporal/entities",
                tenant="test_tenant",
                context=None,
            )

        print("Mintaka request routing: SUCCESS")

        # --------------------------------------------------
        # Test request-specific tenant and context
        # --------------------------------------------------

        context_url = "https://example.org/context.jsonld"

        with patch.object(client, "request") as mock_request:

            orion.request(
                method="GET",
                endpoint="/ngsi-ld/v1/entities",
                tenant="another_tenant",
                context=context_url,
            )

            mock_request.assert_called_once_with(
                service="orion",
                method="GET",
                endpoint="/ngsi-ld/v1/entities",
                tenant="another_tenant",
                context=context_url,
            )

        print("Dynamic tenant and context: SUCCESS")

        print()
        print("[CIRCULOOS] All service client tests passed.")

    finally:
        client.close()


if __name__ == "__main__":
    main()