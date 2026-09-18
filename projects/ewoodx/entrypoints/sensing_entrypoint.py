from pathlib import Path
import sys


PROJECT_ROOT = Path(
    __file__
).resolve().parents[3]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from framework.workspace import (
    DomainManager,
    EntityManager,
    EntryManager,
    EntryPaths,
    WorkspacePaths,
    init_workspace,
    load_workspace,
)

from projects.ewoodx.config import (
    EWOODX_REPOSITORY_ROOT,
    EWOODX_WORKSPACE_LAYOUT,
    SENSING_DOMAIN,
    TIMBER_ENTITY_INDEX,
)

from projects.ewoodx.operations.entry_allocator import (
    EWoodXEntryAllocator,
)

from projects.ewoodx.operations.timber_segmentation_arducam import (
    EWoodXTimberSegmentationArducam,
)

from projects.ewoodx.operations.timber_segmentation_angetube import (
    EWoodXTimberSegmentationAngetube,
)


class EWoodXSensingEntrypoint:
    """
    Start and coordinate one eWoodX sensing process.

    Runtime context may be supplied programmatically
    by project-level orchestration or resolved
    interactively for manual execution.
    """

    def __init__(
        self,
        workspace: WorkspacePaths | None = None,
        entry: EntryPaths | None = None,
        equipment: str | None = None,
    ) -> None:

        if (
            workspace is not None
            and not isinstance(
                workspace,
                WorkspacePaths,
            )
        ):
            raise TypeError(
                "workspace must be a WorkspacePaths "
                "instance or None."
            )

        if (
            entry is not None
            and not isinstance(
                entry,
                EntryPaths,
            )
        ):
            raise TypeError(
                "entry must be an EntryPaths "
                "instance or None."
            )

        if (
            entry is not None
            and workspace is None
        ):
            raise ValueError(
                "workspace must be supplied when "
                "entry is supplied."
            )

        self.workspace = workspace
        self.entry = entry
        self.equipment = equipment

    # -------------------------------------------------------------
    # Workspace
    # -------------------------------------------------------------

    def resolve_workspace(
        self,
    ) -> WorkspacePaths:
        """
        Interactively resolve the workspace used
        by this sensing process.
        """

        while True:

            print()
            print(
                "eWoodX Sensing"
            )

            print(
                "=============="
            )

            print()
            print(
                "Workspace:"
            )

            print(
                "[1] Use last workspace"
            )

            print(
                "[2] Open workspace by name"
            )

            print(
                "[3] Create new workspace"
            )

            print(
                "[4] Exit"
            )

            choice = (
                input(
                    "Select: "
                )
                .strip()
            )

            if choice == "1":

                try:

                    return load_workspace(
                        project_root=(
                            EWOODX_REPOSITORY_ROOT
                        )
                    )

                except FileNotFoundError as error:

                    print()
                    print(
                        f"[eWoodX] {error}"
                    )

            elif choice == "2":

                workspace_name = (
                    input(
                        "Workspace name: "
                    )
                    .strip()
                )

                if not workspace_name:

                    print(
                        "[eWoodX] Workspace "
                        "name cannot be empty."
                    )

                    continue

                try:

                    return load_workspace(
                        project_root=(
                            EWOODX_REPOSITORY_ROOT
                        ),
                        workspace_name=(
                            workspace_name
                        ),
                    )

                except FileNotFoundError as error:

                    print()
                    print(
                        f"[eWoodX] {error}"
                    )

            elif choice == "3":

                workspace_name = (
                    input(
                        "New workspace name: "
                    )
                    .strip()
                )

                if not workspace_name:

                    print(
                        "[eWoodX] Workspace "
                        "name cannot be empty."
                    )

                    continue

                workspace_path = (
                    EWOODX_REPOSITORY_ROOT
                    / "workspaces"
                    / workspace_name
                )

                if workspace_path.exists():

                    print(
                        "[eWoodX] Workspace already "
                        f"exists: {workspace_name}"
                    )

                    print(
                        "[eWoodX] Use option 2 "
                        "to open it."
                    )

                    continue

                return init_workspace(
                    project_root=(
                        EWOODX_REPOSITORY_ROOT
                    ),
                    workspace_name=(
                        workspace_name
                    ),
                    layout=(
                        EWOODX_WORKSPACE_LAYOUT
                    ),
                )

            elif choice == "4":

                raise SystemExit(
                    0
                )

            else:

                print(
                    "[eWoodX] Invalid selection."
                )

    # -------------------------------------------------------------
    # Entry
    # -------------------------------------------------------------

    def resolve_entry(
        self,
        workspace: WorkspacePaths,
    ) -> EntryPaths:
        """
        Resolve the sensing entry used by this process.

        The user may continue the latest managed entry,
        select another existing entry, or create a new
        project-named entry.
        """

        domain_manager = DomainManager(
            workspace=workspace
        )

        sensing_domain = (
            domain_manager.ensure_domain(
                SENSING_DOMAIN
            )
        )

        entry_manager = EntryManager(
            domain=sensing_domain
        )

        entry_allocator = (
            EWoodXEntryAllocator(
                entry_manager=entry_manager
            )
        )

        while True:

            entries = (
                entry_manager.list_entries()
            )

            latest_entry = (
                entry_allocator.latest_entry()
            )

            print()
            print(
                "Sensing entry:"
            )

            if latest_entry is not None:

                print(
                    "[1] Continue latest entry: "
                    f"{latest_entry.entry_name}"
                )

            else:

                print(
                    "[1] Continue latest entry "
                    "(none available)"
                )

            print(
                "[2] Select existing entry"
            )

            print(
                "[3] Create new entry"
            )

            print(
                "[4] Exit"
            )

            choice = (
                input(
                    "Select: "
                )
                .strip()
            )

            if choice == "1":

                if latest_entry is None:

                    print(
                        "[eWoodX] No sensing "
                        "entries exist yet."
                    )

                    continue

                return latest_entry

            elif choice == "2":

                if not entries:

                    print(
                        "[eWoodX] No sensing "
                        "entries exist yet."
                    )

                    continue

                print()
                print(
                    "Available sensing entries:"
                )

                for index, entry in enumerate(
                    entries,
                    start=1,
                ):
                    print(
                        f"[{index}] "
                        f"{entry.entry_name}"
                    )

                selection = (
                    input(
                        "Select entry: "
                    )
                    .strip()
                )

                try:

                    selected_index = (
                        int(selection) - 1
                    )

                except ValueError:

                    print(
                        "[eWoodX] Invalid selection."
                    )

                    continue

                if (
                    selected_index < 0
                    or selected_index >= len(entries)
                ):

                    print(
                        "[eWoodX] Invalid selection."
                    )

                    continue

                return entries[
                    selected_index
                ]

            elif choice == "3":

                entry_name = (
                    entry_allocator.allocate()
                )

                entry = (
                    entry_manager.ensure_entry(
                        entry_name
                    )
                )

                print()
                print(
                    "[eWoodX] Created sensing entry:"
                )

                print(
                    entry.entry_name
                )

                return entry

            elif choice == "4":

                raise SystemExit(
                    0
                )

            else:

                print(
                    "[eWoodX] Invalid selection."
                )

    # -------------------------------------------------------------
    # Equipment
    # -------------------------------------------------------------

    def resolve_equipment(
        self,
    ) -> str:
        """
        Interactively choose the sensing equipment.
        """

        while True:

            print()
            print(
                "Sensing equipment:"
            )

            print(
                "[1] Arducam"
            )

            print(
                "[2] Webcam"
            )

            print(
                "[3] Exit"
            )

            choice = (
                input(
                    "Select: "
                )
                .strip()
            )

            if choice == "1":

                return "arducam"

            elif choice == "2":

                return "webcam"

            elif choice == "3":

                raise SystemExit(
                    0
                )

            else:

                print(
                    "[eWoodX] Invalid selection."
                )

    # -------------------------------------------------------------
    # Run
    # -------------------------------------------------------------

    def run(
        self,
    ) -> None:
        """
        Start the sensing process.

        Missing runtime context is resolved
        interactively. Supplied context is used
        directly, allowing later orchestration
        to invoke the same entrypoint.
        """

        if self.workspace is None:

            self.workspace = (
                self.resolve_workspace()
            )

        if self.entry is None:

            self.entry = (
                self.resolve_entry(
                    workspace=(
                        self.workspace
                    )
                )
            )

        entity_manager = EntityManager(
            workspace=self.workspace,
            entry=self.entry,
            index_schema=TIMBER_ENTITY_INDEX,
        )

        if self.equipment is None:

            self.equipment = (
                self.resolve_equipment()
            )

        equipment = (
            self.equipment
            .strip()
            .lower()
        )

        print()
        print(
            "[eWoodX] Active workspace:"
        )

        print(
            self.workspace.root
        )

        print(
            "[eWoodX] Active sensing entry:"
        )

        print(
            self.entry.root
        )

        print(
            "[eWoodX] Sensing equipment:"
        )

        print(
            equipment
        )

        # ---------------------------------------------------------
        # Temporary operation construction.
        #
        # The segmentation operations still use the old workspace
        # artifact layout. Their persistence interface will be
        # migrated to EntityManager in the next step.
        # ---------------------------------------------------------

        if equipment == "arducam":

            operation = (
                EWoodXTimberSegmentationArducam(
                    entity_manager=entity_manager
                )
            )

        elif equipment == "webcam":

            operation = (
                EWoodXTimberSegmentationAngetube(
                    entity_manager=entity_manager
                )
            )

        else:

            raise ValueError(
                "Unknown sensing equipment: "
                f"{equipment}"
            )

        operation.run()


def main(
) -> None:

    entrypoint = (
        EWoodXSensingEntrypoint()
    )

    entrypoint.run()


if __name__ == "__main__":
    main()