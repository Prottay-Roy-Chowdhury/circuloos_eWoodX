"""Test CIRCULOOS adapter configuration."""

from pathlib import Path
import sys


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
)


def main() -> None:

    print()
    print("[CIRCULOOS] Configuration Test")
    print("-" * 40)

    config = CirculoosConfig.from_partner_file()

    print(f"Host: {config.host}")
    print(f"Orion URL: {config.orion_url}")
    print(f"Mintaka URL: {config.mintaka_url}")

    client = CirculoosClient(
        config=config,
    )

    try:
        print("Client initialization: SUCCESS")
    finally:
        client.close()

    print()
    print("[CIRCULOOS] Configuration test passed.")


if __name__ == "__main__":
    main()
