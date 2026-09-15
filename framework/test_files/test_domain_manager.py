from pathlib import Path
import shutil
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


from framework.workspace import (
    DomainManager,
    init_workspace,
    load_workspace,
)


TEST_PROJECT_ROOT = (
    PROJECT_ROOT
    / "test_file_transfer_data"
    / "test_data"
    / "domain_test_project"
)


def main() -> None:

    # --------------------------------------------------
    # Phase 1: Create workspace and domains
    # --------------------------------------------------

    if TEST_PROJECT_ROOT.exists():
        shutil.rmtree(
            TEST_PROJECT_ROOT
        )

    workspace = init_workspace(
        project_root=TEST_PROJECT_ROOT,
        workspace_name="test_workspace",
        layout={},
    )

    manager = DomainManager(
        workspace=workspace
    )

    manager.ensure_domain(
        "sensing"
    )

    manager.ensure_domain(
        "design"
    )

    manager.ensure_domain(
        "robot_control"
    )

    domains = manager.list_domains()

    domain_names = [
        domain.domain_name
        for domain in domains
    ]

    assert domain_names == [
        "design",
        "robot_control",
        "sensing",
    ]

    print()
    print("Phase 1 - Created workspace:")
    print(workspace.root)

    print()
    print("Created domains:")

    for domain in domains:
        print(
            f"  {domain.domain_name}: "
            f"{domain.root}"
        )

    # --------------------------------------------------
    # Simulate program ending
    # --------------------------------------------------

    del manager
    del workspace
    del domains

    # --------------------------------------------------
    # Phase 2: Reload everything from disk
    # --------------------------------------------------

    workspace = load_workspace(
        project_root=TEST_PROJECT_ROOT,
        workspace_name="test_workspace",
    )

    manager = DomainManager(
        workspace=workspace
    )

    domains = manager.list_domains()

    domain_names = [
        domain.domain_name
        for domain in domains
    ]

    assert domain_names == [
        "design",
        "robot_control",
        "sensing",
    ]

    assert manager.exists(
        "sensing"
    )

    sensing = manager.load_domain(
        "sensing"
    )

    assert sensing.domain_name == "sensing"
    assert sensing.root.exists()
    assert sensing.manifest.exists()

    print()
    print("Phase 2 - Reloaded workspace:")
    print(workspace.root)

    print()
    print("Recovered domains:")

    for domain in domains:
        print(
            f"  {domain.domain_name}: "
            f"{domain.root}"
        )

    print()
    print("Recovered sensing domain:")
    print(sensing.root)

    print()
    print(
        "Domain persistence test passed."
    )


if __name__ == "__main__":
    main()