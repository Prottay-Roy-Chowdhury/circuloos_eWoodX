"""Standalone test for the eWoodX CIRCULOOS entity registry."""

from pathlib import Path
import sys
import json

# Allow execution directly from the repository.
REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPOSITORY_ROOT))

from framework.workspace import (
    load_workspace,
    DomainManager,
    EntryManager,
    EntityManager,
)

from projects.ewoodx.config.workspace import (
    EWOODX_REPOSITORY_ROOT,
    EWOODX_WORKSPACE_LAYOUT,
)

from projects.ewoodx.config.entity import (
    TIMBER_ENTITY_INDEX,
)

from projects.ewoodx.operations.circuloos_adapter.entity_registry import (
    CirculoosEntityRegistry,
)


# -------------------------------------------------------------
# Test configuration
# -------------------------------------------------------------

WORKSPACE_NAME = "test_0923"
TIMBER_ID = "T-0001-WAR"

# Set True only if you want to allocate a new advertisement.
ALLOCATE_ADVERTISEMENT = True


# -------------------------------------------------------------
# EntityManager initialization
# -------------------------------------------------------------

def load_entity_manager(
    workspace_name: str,
) -> EntityManager:

    workspace = load_workspace(
        project_root=EWOODX_REPOSITORY_ROOT,
        workspace_name=workspace_name,
        layout=EWOODX_WORKSPACE_LAYOUT,
    )

    domain_manager = DomainManager(
        workspace=workspace,
    )

    # EntityManager's index is workspace-wide.
    # We only need one existing entry to initialize it.
    for domain in domain_manager.list_domains():

        entry_manager = EntryManager(
            domain=domain,
        )

        entries = entry_manager.list_entries()

        if entries:
            return EntityManager(
                workspace=workspace,
                entry=entries[0],
                index_schema=TIMBER_ENTITY_INDEX,
            )

    raise FileNotFoundError(
        f"No existing entries found in workspace: "
        f"{workspace_name}"
    )


# -------------------------------------------------------------
# Test
# -------------------------------------------------------------

def main():

    entity_manager = load_entity_manager(
        WORKSPACE_NAME
    )

    print("Workspace:", entity_manager.workspace.root)

    # Confirm the timber exists.
    timber = entity_manager.load_entity(
        TIMBER_ID
    )

    print("Timber directory:", timber.root)

    registry = CirculoosEntityRegistry(
        entity_manager=entity_manager
    )

    # Create or reuse the Wood registry.
    data = registry.ensure(
        TIMBER_ID
    )

    print("\nWood URN:", data["wood"]["urn"])
    print("Wood status:", data["wood"]["status"])

    # Confirm persistent identity.
    again = registry.ensure(
        TIMBER_ID
    )

    assert (
        again["wood"]["urn"]
        == data["wood"]["urn"]
    )

    print("Wood URN persistence: PASS")

    if ALLOCATE_ADVERTISEMENT:

        ad = registry.allocate_advertisement(
            TIMBER_ID
        )

        print("\nAdvertisement URN:", ad["urn"])
        print("refMaterial:", ad["ref_material"])

    saved = registry.load(
        TIMBER_ID
    )

    print("\nSaved registry:")
    print(
        json.dumps(
            saved,
            indent=2,
        )
    )

    print("\nRegistry path:", registry.registry_path(TIMBER_ID))
    print("Registry test: PASS")


if __name__ == "__main__":
    main()