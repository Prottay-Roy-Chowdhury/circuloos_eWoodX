"""Isolated eWoodX Wood -> RAMP refMaterial integration test.

Place this file in projects/ewoodx/operations/circuloos_adapter/tests/.
Default action is preview. No existing entity is updated.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(PROJECT_ROOT))
from projects.ewoodx.operations.circuloos_adapter import CirculoosConfig, CirculoosClient, OrionClient

TENANT = 'circuloos_ewoodx_material'
TEMPLATE_ID = 'urn:ngsi-ld:others:54b8895d-774d-41ee-91b0-01af0ef77dd0'
WOOD_ID = 'urn:ngsi-ld:wood:ewoodx-refmaterial-test-001'
AD_ID = 'urn:ngsi-ld:others:ewoodx-refmaterial-test-001'
OUTPUT = Path(__file__).resolve().parent / 'refmaterial_test_data'
WOOD_CONTEXT = 'https://raw.githubusercontent.com/european-dynamics-rnd/CIRCULOOS_Data_model/main/material/wood/context.jsonld'
RAMP_CONTEXT = 'http://circuloos-ld-context/circuloos-context.jsonld'


def prop(value, unit=None):
    result = {'type': 'Property', 'value': value}
    if unit:
        result['unitCode'] = unit
    return result


def build(template):
    wood = {
        'id': WOOD_ID, 'type': 'wood',
        'length': prop(525.1, 'MMT'),
        'width': prop(46.95, 'MMT'),
        'quantity': prop(0.02392246, 'MTK'),
        'color': prop('#D1BBB0'),
        # Avoid thickness: the sensed 2 mm may be a placeholder.
    }
    ad = deepcopy(template)
    ad['id'] = AD_ID
    # Reuse the known eWoodX listing's RAMP classification, owner and facility.
    # These are NOT validated as the correct classification for individual timber.
    now = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    ad['materialAdTitle'] = prop('[TEST] eWoodX timber refMaterial link')
    ad['materialDescription'] = prop('Temporary CIRCULOOS integration test. Not a commercial offer.')
    ad['materialQuantity'] = prop(0.02392246, 'MTK')
    ad['physicalFormCategory'] = prop('bySurface')
    ad['materialPrice'] = prop(0)
    ad['materialAdStatus'] = prop('Open')
    ad['materialAdType'] = prop('Sell')
    ad['refMaterial'] = {'type': 'Relationship', 'object': WOOD_ID, 'observedAt': now}
    ad['availableFrom'] = prop(datetime.now(timezone.utc).date().isoformat())
    ad['imageURL'] = prop('')
    # Remove inherited observedAt values that refer to a different listing.
    for value in ad.values():
        if isinstance(value, dict) and 'observedAt' in value:
            value['observedAt'] = now
    wood.pop('@context', None)
    ad.pop('@context', None)
    return wood, ad


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action', choices=['preview', 'publish', 'verify', 'cleanup'], default='preview')
    parser.add_argument('--confirm', action='store_true', help='Required for publish or cleanup')
    args = parser.parse_args()
    if args.action in ('publish', 'cleanup') and not args.confirm:
        parser.error('--confirm is required for publish or cleanup')

    client = CirculoosClient(CirculoosConfig.from_partner_file())
    orion = OrionClient(client)
    OUTPUT.mkdir(exist_ok=True)
    try:
        if args.action in ('preview', 'publish'):
            template = orion.get_entity(TEMPLATE_ID, tenant=TENANT)
            wood, ad = build(template)
            for name, entity in [('wood.json', wood), ('ramp_ad.json', ad)]:
                (OUTPUT / name).write_text(json.dumps([entity], indent=2), encoding='utf-8')
            print('Generated:', OUTPUT)
            print('WARNING: classification and ownership are inherited from the existing eWoodX listing.')
            print('Inspect both files before using --action publish --confirm.')
            if args.action == 'preview':
                return
            # Guard against accidental overwrites; unlike upsert, create returns conflict.
            for entity in (wood, ad):
                try:
                    orion.get_entity(entity['id'], tenant=TENANT)
                except Exception as exc:
                    if getattr(exc, 'status_code', None) != 404:
                        raise
                else:
                    raise RuntimeError('Test entity already exists: ' + entity['id'])
            # Send one entity per upsert so the relationship target exists first.
            orion.upsert_entities([wood], tenant=TENANT, context=WOOD_CONTEXT)
            print('Wood created:', WOOD_ID)
            orion.upsert_entities([ad], tenant=TENANT, context=RAMP_CONTEXT)
            print('Advertisement created:', AD_ID)

        if args.action in ('publish', 'verify'):
            wood_result = orion.get_entity(WOOD_ID, tenant=TENANT)
            ad_result = orion.get_entity(AD_ID, tenant=TENANT)
            ref = ad_result.get('refMaterial', {})
            if ref.get('object') != WOOD_ID:
                raise AssertionError(f'Unexpected refMaterial: {ref}')
            print("Wood entity ID:", wood_result["id"])
            print("Wood entity type:", wood_result["type"])
            print("Advertisement type:", ad_result["type"])
            print("refMaterial:", json.dumps(ref, indent=2))

            # Save the responses before checking their types.
            (OUTPUT / "wood_readback.json").write_text(
                json.dumps(wood_result, indent=2),
                encoding="utf-8",
            )
            (OUTPUT / "ramp_ad_readback.json").write_text(
                json.dumps(ad_result, indent=2),
                encoding="utf-8",
            )
            (OUTPUT / 'wood_readback.json').write_text(json.dumps(wood_result, indent=2), encoding='utf-8')
            (OUTPUT / 'ramp_ad_readback.json').write_text(json.dumps(ad_result, indent=2), encoding='utf-8')
            print('PASS: Orion readback confirms refMaterial points to the Wood entity.')
            print('NEXT: Inspect RAMP UI manually; Orion readback does not verify UI behavior.')

        if args.action == 'cleanup':
            for entity_id in (AD_ID, WOOD_ID):
                orion.delete_entity(entity_id, tenant=TENANT)
                print('Deleted:', entity_id)
    finally:
        client.close()


if __name__ == '__main__':
    main()
