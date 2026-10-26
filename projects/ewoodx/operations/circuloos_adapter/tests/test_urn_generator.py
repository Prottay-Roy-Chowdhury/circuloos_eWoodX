from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(PROJECT_ROOT))

from projects.ewoodx.operations.circuloos_adapter.urn_generator import (
    CirculoosURNGenerator,
)

generator = CirculoosURNGenerator()

timber_id = "T-0001-WAR"

wood = generator.wood_urn(timber_id)
ad_1 = generator.advertisement_urn(timber_id, 1)
ad_2 = generator.advertisement_urn(timber_id, 2)

print("Timber:", timber_id)
print("Wood:", wood)
print("Advertisement 1:", ad_1)
print("Advertisement 2:", ad_2)

assert wood == "urn:ngsi-ld:wood:ewoodx-T-0001-WAR"
assert ad_1 == "urn:ngsi-ld:others:ewoodx-T-0001-WAR-AD-001"
assert ad_2 == "urn:ngsi-ld:others:ewoodx-T-0001-WAR-AD-002"

print("PASS: URN generation successful.")
