"""Configuration for the eWoodX CIRCULOOS adapter."""

from dataclasses import dataclass
from pathlib import Path


ADAPTER_ROOT = Path(__file__).resolve().parent

PARTNER_VARIABLES_FILE = ADAPTER_ROOT / "partner_variables.txt"

ORION_TOKEN_FILE = ADAPTER_ROOT / "token.txt"
MINTAKA_TOKEN_FILE = ADAPTER_ROOT / "tokenMintaka.txt"

# ------------------------------------------------------------------
# RAMP advertisement mapping defaults
# ------------------------------------------------------------------

RAMP_OWNER_URN = (
    "urn:ngsi-ld:ownedBy:ewoodx_material:"
    "241d9bbb-4255-4238-8c06-fb9f30cf0a04"
)

RAMP_PRODUCTION_FACILITY_URN = (
    "urn:ngsi-ld:productionFacility:wood_panel_01:"
    "6c0b8d78-9158-418a-aef8-c259cd68b972"
)

RAMP_COUNTRY = "Spain"

RAMP_AD_TYPE = "Sell"
RAMP_AD_STATUS = "Open"
RAMP_PHYSICAL_FORM = "bySurface"

def load_partner_variables(
    path: Path = PARTNER_VARIABLES_FILE,
) -> dict[str, str]:
    """Read the KEY=VALUE format used by CIRCULOOS Bash scripts."""

    if not path.is_file():
        raise FileNotFoundError(
            f"CIRCULOOS partner variables file not found: {path}"
        )

    variables = {}

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        key, separator, value = line.partition("=")

        if not separator:
            raise ValueError(
                f"Invalid partner variable at line {line_number}"
            )

        variables[key.strip()] = (
            value.strip().strip('"').strip("'")
        )

    return variables


@dataclass(frozen=True)
class CirculoosConfig:
    host: str
    username: str
    password: str
    orion_secret: str
    mintaka_secret: str
    timeout: float = 30.0

    @classmethod
    def from_partner_file(
        cls,
        path: Path = PARTNER_VARIABLES_FILE,
    ) -> "CirculoosConfig":

        variables = load_partner_variables(path)

        def required(key: str) -> str:
            value = variables.get(key, "").strip()

            if not value:
                raise ValueError(
                    f"Missing required partner variable: {key}"
                )

            return value

        return cls(
            host=required("HOST")
                .removeprefix("https://")
                .removeprefix("http://")
                .rstrip("/"),
            username=required("PARTNER_USERNAME"),
            password=required("PARTNER_PASSWORD"),
            orion_secret=required("ORION_PEP_SECRET"),
            mintaka_secret=required("MIKTAKA_PEP_SECRET"),
            timeout=float(variables.get("TIMEOUT", "30")),
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
