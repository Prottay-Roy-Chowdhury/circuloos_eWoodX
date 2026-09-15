from pathlib import Path
import shutil
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


from framework.workspace import (
    DomainManager,
    EntryManager,
    init_workspace,
    load_workspace,
)


TEST_PROJECT_ROOT = (
    PROJECT_ROOT
    / "test_file_transfer_data"
    / "test_data"
    / "entry_test_project"
)


# --------------------------------------------------
# Clean previous test data
# --------------------------------------------------

if TEST_PROJECT_ROOT.exists():
    shutil.rmtree(TEST_PROJECT_ROOT)


# --------------------------------------------------
# Phase 1: Create workspace and domain
# --------------------------------------------------

workspace = init_workspace(
    project_root=TEST_PROJECT_ROOT,
    workspace_name="test_workspace",
    layout={},
)

domain_manager = DomainManager(
    workspace=workspace,
)

domain = domain_manager.ensure_domain(
    "sensing"
)

print("Phase 1 - Created domain:")
print(domain.root)


# --------------------------------------------------
# Phase 2: Create entries
# --------------------------------------------------

entry_manager = EntryManager(
    domain=domain,
)

entry_1 = entry_manager.ensure_entry(
    "test_entry_001"
)

entry_2 = entry_manager.ensure_entry(
    "test_entry_002"
)

assert entry_1.root.exists()
assert entry_1.manifest.is_file()

assert entry_2.root.exists()
assert entry_2.manifest.is_file()

assert entry_manager.exists(
    "test_entry_001"
)

assert entry_manager.exists(
    "test_entry_002"
)

entries = entry_manager.list_entries()

entry_names = [
    entry.entry_name
    for entry in entries
]

assert entry_names == [
    "test_entry_001",
    "test_entry_002",
]

print()
print("Phase 2 - Created entries:")

for entry in entries:
    print(
        f"  {entry.entry_name}: "
        f"{entry.root}"
    )


# --------------------------------------------------
# Phase 3: Simulate restart
# --------------------------------------------------

del entry_1
del entry_2
del entries
del entry_manager
del domain
del domain_manager
del workspace


workspace = load_workspace(
    project_root=TEST_PROJECT_ROOT,
    workspace_name="test_workspace",
)

domain_manager = DomainManager(
    workspace=workspace,
)

domain = domain_manager.load_domain(
    "sensing"
)

entry_manager = EntryManager(
    domain=domain,
)

print()
print("Phase 3 - Reloaded hierarchy:")
print(f"  Workspace: {workspace.root}")
print(f"  Domain:    {domain.root}")


# --------------------------------------------------
# Phase 4: Recover entries from disk
# --------------------------------------------------

entries = entry_manager.list_entries()

entry_names = [
    entry.entry_name
    for entry in entries
]

assert entry_names == [
    "test_entry_001",
    "test_entry_002",
]

recovered_entry = entry_manager.load_entry(
    "test_entry_002"
)

assert (
    recovered_entry.entry_name
    == "test_entry_002"
)

assert recovered_entry.root.exists()
assert recovered_entry.manifest.is_file()

assert entry_manager.exists(
    "test_entry_001"
)

assert entry_manager.exists(
    "test_entry_002"
)

print()
print("Phase 4 - Recovered entries:")

for entry in entries:
    print(
        f"  {entry.entry_name}: "
        f"{entry.root}"
    )


# --------------------------------------------------
# Phase 5: Verify unmanaged directory is ignored
# --------------------------------------------------

unmanaged = (
    domain.root
    / "random_directory"
)

unmanaged.mkdir()

assert not entry_manager.exists(
    "random_directory"
)

entries = entry_manager.list_entries()

entry_names = [
    entry.entry_name
    for entry in entries
]

assert "random_directory" not in entry_names

print()
print(
    "Phase 5 - Unmanaged directory correctly ignored."
)


print()
print(
    "Entry manager persistence test passed."
)