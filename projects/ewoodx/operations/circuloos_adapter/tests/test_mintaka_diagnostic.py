"""Compare Mintaka temporal queries with and without lastN."""

from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(PROJECT_ROOT))

from projects.ewoodx.operations.circuloos_adapter import (
    CirculoosConfig,
    CirculoosClient,
    MintakaClient,
    CirculoosHTTPError,
)

TENANT = "circuloos_ewoodx_material"

ENTITY_ID = (
    "urn:ngsi-ld:EwoodxIntegrationTest:"
    "a2845fe0-51b0-441b-8d8e-404cb27d1ced"
)


def main():

    config = CirculoosConfig.from_partner_file()
    client = CirculoosClient(config=config)
    mintaka = MintakaClient(client=client)

    endpoint = (
        "/temporal/entities/"
        + client.encode_entity_id(ENTITY_ID)
    )

    queries = [
        ("Without parameters", None),
        ("With lastN=10", {"lastN": 10}),
    ]

    try:
        for label, params in queries:

            print()
            print("=" * 55)
            print(label)
            print("=" * 55)

            try:
                response = mintaka.request(
                    method="GET",
                    endpoint=endpoint,
                    tenant=TENANT,
                    params=params,
                    accept="application/ld+json",
                )

                print("HTTP status:", response.status_code)
                print("Request URL:", response.url)
                print("Content-Type:", response.headers.get("Content-Type"))

                data = response.json()
                print(json.dumps(data, indent=2))

                attributes = [
                    key for key in data
                    if key not in ("id", "type", "@context")
                ]

                print("Temporal attributes:", attributes)

                if not attributes:
                    print("No temporal attributes returned.")

            except CirculoosHTTPError as exc:
                print("Request failed:", exc)

    finally:
        client.close()


if __name__ == "__main__":
    main()
