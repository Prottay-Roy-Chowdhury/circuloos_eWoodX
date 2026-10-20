"""Test CIRCULOOS Keycloak authentication."""

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
    CirculoosAuth,
)

from projects.ewoodx.operations.circuloos_adapter.config import (
    ORION_TOKEN_FILE,
    MINTAKA_TOKEN_FILE,
)


def main() -> None:

    print()
    print("[CIRCULOOS] Authentication Test")
    print("-" * 40)

    config = CirculoosConfig.from_partner_file()

    auth = CirculoosAuth(
        config=config,
    )

    try:

        for service, token_file in (
            ("orion", ORION_TOKEN_FILE),
            ("mintaka", MINTAKA_TOKEN_FILE),
        ):

            print()
            print(f"Authenticating: {service}")

            token = auth.get_token(
                service=service,
                force_refresh=True,
            )

            if not token_file.is_file():
                raise RuntimeError(
                    f"Token file not created: {token_file}"
                )

            stored_token = token_file.read_text(
                encoding="utf-8"
            )

            if stored_token != token:
                raise RuntimeError(
                    f"Stored token mismatch for {service}"
                )

            print("Authentication: SUCCESS")
            print(f"Token file: {token_file.name}")
            print("Token file verification: SUCCESS")

        print()
        print("[CIRCULOOS] All authentication tests passed.")

    finally:
        auth.close()


if __name__ == "__main__":
    main()
