"""Configuration for the eWoodX CIRCULOOS adapter."""

from dataclasses import dataclass
import os
from pathlib import Path

ADAPTER_ROOT = Path(__file__).resolve().parent


def load_env_file(path: Path | None = None) -> None:
    """Load simple KEY=VALUE entries without overriding the environment."""
    path = path or ADAPTER_ROOT / ".env"

    if not path.is_file():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        key, separator, value = line.partition("=")

        if not separator:
            raise ValueError(f"Invalid environment entry: {key}")

        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if not key:
            raise ValueError("Empty environment variable name.")

        os.environ.setdefault(key, value)


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()

    if not value:
        raise ValueError(
            f"Missing CIRCULOOS configuration: {name}"
        )

    return value


@dataclass(frozen=True)
class CirculoosConfig:
    host: str
    tenant: str
    username: str
    password: str
    orion_secret: str
    mintaka_secret: str
    context: str | None = None
    timeout: float = 30.0

    @classmethod
    def from_env(cls, env_file: Path | None = None):
        load_env_file(env_file)

        return cls(
            host=required_env("CIRCULOOS_HOST")
                .removeprefix("https://")
                .removeprefix("http://")
                .rstrip("/"),
            tenant=required_env("CIRCULOOS_TENANT"),
            username=required_env("CIRCULOOS_USERNAME"),
            password=required_env("CIRCULOOS_PASSWORD"),
            orion_secret=required_env("CIRCULOOS_ORION_PEP_SECRET"),
            mintaka_secret=required_env("CIRCULOOS_MINTAKA_PEP_SECRET"),
            context=os.getenv("CIRCULOOS_CONTEXT") or None,
            timeout=float(os.getenv("CIRCULOOS_TIMEOUT", "30")),
        )

    @property
    def base_url(self) -> str:
        return f"https://{self.host}"

    @property
    def token_url(self) -> str:
        return (
            f"{self.base_url}/idm/realms/fiware-server/"
            "protocol/openid-connect/token"
        )

    @property
    def orion_url(self) -> str:
        return f"{self.base_url}/kong/keycloak-orion"

    @property
    def mintaka_url(self) -> str:
        return f"{self.base_url}/kong/keycloak-mintaka"
