"""
eWoodX sensing entrypoint for the unified sensing composer.

This is a separate entrypoint. The original
sensing_entrypoint.py remains unchanged.

Preserves:
    - Existing workspace resolution
    - Existing sensing domain and entry resolution
    - Existing entry allocation
    - Existing equipment selection
    - Existing EntityManager initialization

Adds:
    - Single/multi segmentation mode selection
    - Composer configuration
    - Optional sensing streaming
    - Optional handdraw detection

CIRCULOOS publication is not enabled here.
"""

from pathlib import Path
import sys
import argparse


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

from projects.ewoodx.operations.sensing_composer import (
    EWoodXSensingComposer,
)

# =============================================================
# SENSING RUNTIME CONFIGURATION
# =============================================================

ENABLE_HANDDRAW = False
ENABLE_STREAMING = True
ENABLE_PREVIEW = True
ENABLE_SYNCHRONIZATION = False


class EWoodXSensingEntrypointStream:
    """
    Start and coordinate one eWoodX sensing process
    using the unified sensing composer.

    Runtime context may be supplied programmatically
    by project-level orchestration or resolved
    interactively for manual execution.
    """

    def __init__(
        self,
        workspace: WorkspacePaths | None = None,
        entry: EntryPaths | None = None,
        equipment: str | None = None,
        segmentation_mode: str | None = None,
        enable_handdraw: bool = ENABLE_HANDDRAW,
        enable_streaming: bool = ENABLE_STREAMING,
        enable_preview: bool = ENABLE_PREVIEW,
        intrinsic_file: Path | None = None,
        enable_synchronization: bool = ENABLE_SYNCHRONIZATION,
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

        # New composer configuration.
        self.segmentation_mode = segmentation_mode
        self.enable_handdraw = bool(enable_handdraw)
        self.enable_streaming = bool(enable_streaming)
        self.enable_preview = bool(enable_preview)

        self.enable_synchronization = bool(
            enable_synchronization
        )

        if self.enable_synchronization and not self.enable_streaming:

            raise ValueError(
                "Sensing synchronization requires streaming."
            )

        self.intrinsic_file = (
            Path(intrinsic_file)
            if intrinsic_file is not None
            else None
        )

    # -------------------------------------------------------------
    # Workspace
    # -------------------------------------------------------------

    def resolve_workspace(
        self,
        mode: str | None = None,
        workspace_name: str | None = None,
    ) -> WorkspacePaths:
        """
        Resolve the workspace used by this sensing process.

        Modes:
            last
            existing
            new

        If mode is None, resolve interactively.
        """

        # ---------------------------------------------------------
        # Non-interactive resolution
        # ---------------------------------------------------------

        if mode is not None:

            if mode == "last":

                return load_workspace(
                    project_root=EWOODX_REPOSITORY_ROOT,
                )

            if mode not in ("existing", "new"):

                raise ValueError(
                    f"Unknown workspace mode: {mode}"
                )

            workspace_name = (
                workspace_name or ""
            ).strip()

            if not workspace_name:

                raise ValueError(
                    "Workspace name cannot be empty."
                )

            if (
                workspace_name in (".", "..")
                or "/" in workspace_name
                or "\\" in workspace_name
                or ":" in workspace_name
            ):

                raise ValueError(
                    "Workspace name must be a directory name."
                )

            if mode == "existing":

                return load_workspace(
                    project_root=EWOODX_REPOSITORY_ROOT,
                    workspace_name=workspace_name,
                )

            workspace_path = (
                EWOODX_REPOSITORY_ROOT
                / "workspaces"
                / workspace_name
            )

            if workspace_path.exists():

                raise FileExistsError(
                    f"Workspace already exists: "
                    f"{workspace_name}"
                )

            return init_workspace(
                project_root=EWOODX_REPOSITORY_ROOT,
                workspace_name=workspace_name,
                layout=EWOODX_WORKSPACE_LAYOUT,
            )

        # ---------------------------------------------------------
        # Interactive resolution
        # ---------------------------------------------------------

        while True:

            print()
            print("eWoodX Sensing")
            print("==============")

            print()
            print("Workspace:")
            print("[1] Use last workspace")
            print("[2] Open workspace by name")
            print("[3] Create new workspace")
            print("[4] Exit")

            choice = input("Select: ").strip()

            try:

                if choice == "1":

                    return self.resolve_workspace(
                        mode="last",
                    )

                elif choice == "2":

                    name = input(
                        "Workspace name: "
                    ).strip()

                    return self.resolve_workspace(
                        mode="existing",
                        workspace_name=name,
                    )

                elif choice == "3":

                    name = input(
                        "New workspace name: "
                    ).strip()

                    return self.resolve_workspace(
                        mode="new",
                        workspace_name=name,
                    )

                elif choice == "4":

                    raise SystemExit(0)

                else:

                    print(
                        "[eWoodX] Invalid selection."
                    )

            except (
                FileNotFoundError,
                FileExistsError,
                ValueError,
            ) as error:

                print()
                print(f"[eWoodX] {error}")

    # -------------------------------------------------------------
    # Entry
    # -------------------------------------------------------------

    def resolve_entry(
        self,
        workspace: WorkspacePaths,
        mode: str | None = None,
        entry_name: str | None = None,
    ) -> EntryPaths:
        """
        Resolve the sensing entry used by this process.

        Modes:
            latest
            existing
            new

        If mode is None, resolve interactively.
        """

        domain_manager = DomainManager(
            workspace=workspace,
        )

        sensing_domain = (
            domain_manager.ensure_domain(
                SENSING_DOMAIN,
            )
        )

        entry_manager = EntryManager(
            domain=sensing_domain,
        )

        entry_allocator = EWoodXEntryAllocator(
            entry_manager=entry_manager,
        )

        # ---------------------------------------------------------
        # Shared entry resolution
        # ---------------------------------------------------------

        def resolve_selection(
            selected_mode: str,
            selected_name: str | None = None,
        ) -> EntryPaths:

            if selected_mode == "latest":

                latest_entry = (
                    entry_allocator.latest_entry()
                )

                if latest_entry is None:

                    raise FileNotFoundError(
                        "No sensing entries exist yet."
                    )

                return latest_entry

            elif selected_mode == "existing":

                selected_name = (
                    selected_name or ""
                ).strip()

                if not selected_name:

                    raise ValueError(
                        "Entry name cannot be empty."
                    )

                entries = (
                    entry_manager.list_entries()
                )

                for existing_entry in entries:

                    if (
                        existing_entry.entry_name
                        == selected_name
                    ):

                        return existing_entry

                raise FileNotFoundError(
                    f"Sensing entry not found: "
                    f"{selected_name}"
                )

            elif selected_mode == "new":

                new_entry_name = (
                    entry_allocator.allocate()
                )

                entry = entry_manager.ensure_entry(
                    new_entry_name,
                )

                print()
                print(
                    "[eWoodX] Created sensing entry:"
                )

                print(entry.entry_name)

                return entry

            raise ValueError(
                f"Unknown entry mode: {selected_mode}"
            )

        # ---------------------------------------------------------
        # Non-interactive resolution
        # ---------------------------------------------------------

        if mode is not None:

            return resolve_selection(
                selected_mode=mode,
                selected_name=entry_name,
            )

        # ---------------------------------------------------------
        # Interactive resolution
        # ---------------------------------------------------------

        while True:

            entries = (
                entry_manager.list_entries()
            )

            latest_entry = (
                entry_allocator.latest_entry()
            )

            print()
            print("Sensing entry:")

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

            print("[2] Select existing entry")
            print("[3] Create new entry")
            print("[4] Exit")

            choice = input("Select: ").strip()

            try:

                if choice == "1":

                    return resolve_selection(
                        selected_mode="latest",
                    )

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

                    selection = input(
                        "Select entry: "
                    ).strip()

                    try:

                        selected_index = (
                            int(selection) - 1
                        )

                    except ValueError:

                        print(
                            "[eWoodX] Invalid selection."
                        )

                        continue

                    if not (
                        0 <= selected_index < len(entries)
                    ):

                        print(
                            "[eWoodX] Invalid selection."
                        )

                        continue

                    return resolve_selection(
                        selected_mode="existing",
                        selected_name=(
                            entries[selected_index]
                            .entry_name
                        ),
                    )

                elif choice == "3":

                    return resolve_selection(
                        selected_mode="new",
                    )

                elif choice == "4":

                    raise SystemExit(0)

                else:

                    print(
                        "[eWoodX] Invalid selection."
                    )

            except (
                FileNotFoundError,
                ValueError,
            ) as error:

                print()
                print(f"[eWoodX] {error}")

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
    # Segmentation mode (NEW)
    # -------------------------------------------------------------

    def resolve_segmentation_mode(
        self,
    ) -> str:
        """
        Choose exactly one segmentation mode.

        The composer initializes and runs only
        the selected segmenter.
        """

        while True:

            print()
            print(
                "Segmentation mode:"
            )

            print(
                "[1] Single timber"
            )

            print(
                "[2] Multiple timbers"
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

                return "single"

            elif choice == "2":

                return "multi"

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
        workspace_mode: str | None = None,
        workspace_name: str | None = None,
        entry_mode: str | None = None,
        entry_name: str | None = None,
    ) -> None:
        """
        Start the sensing process using EWoodXSensingComposer.

        Runtime context may be supplied programmatically,
        resolved using startup arguments, or selected
        interactively.
        """

        if self.workspace is None:

            self.workspace = self.resolve_workspace(
                mode=workspace_mode,
                workspace_name=workspace_name,
            )

        if self.entry is None:

            self.entry = self.resolve_entry(
                workspace=self.workspace,
                mode=entry_mode,
                entry_name=entry_name,
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

        if equipment not in (
            "arducam",
            "webcam",
        ):
            raise ValueError(
                "Unknown sensing equipment: "
                f"{equipment}"
            )

        # New: select the segmentation mode
        # before constructing the composer.
        if self.segmentation_mode is None:

            self.segmentation_mode = (
                self.resolve_segmentation_mode()
            )

        segmentation_mode = (
            self.segmentation_mode
            .strip()
            .lower()
        )

        if segmentation_mode not in (
            "single",
            "multi",
        ):
            raise ValueError(
                "Unknown segmentation mode: "
                f"{segmentation_mode}"
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

        print(
            "[eWoodX] Segmentation mode:"
        )

        print(
            segmentation_mode
        )

        print()
        print(
            "[eWoodX] Composer configuration:"
        )

        print(
            f"  Handdraw detection: "
            f"{self.enable_handdraw}"
        )

        print(
            f"  Streaming: "
            f"{self.enable_streaming}"
        )

        print(
            f"  Preview: "
            f"{self.enable_preview}"
        )

        print(
            f"  Capture synchronization: "
            f"{self.enable_synchronization}"
        )

        # ---------------------------------------------------------
        # Unified sensing composer (NEW)
        # ---------------------------------------------------------

        composer = EWoodXSensingComposer(
            entity_manager=entity_manager,
            equipment=equipment,
            segmentation_mode=segmentation_mode,
            intrinsic_file=self.intrinsic_file,
            enable_handdraw=self.enable_handdraw,
            enable_streaming=self.enable_streaming,
            enable_preview=self.enable_preview,

            enable_synchronization=(
                self.enable_synchronization
            ),

            # Optional CIRCULOOS publication will be
            # connected here later, after local testing.
            on_entity_finalized=None,
        )

        composer.run()
        
# =============================================================
# COMMAND LINE INTERFACE
# =============================================================

def parse_arguments(
    argv: list[str] | None = None,
) -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "eWoodX unified sensing entrypoint."
        ),
    )

    # ---------------------------------------------------------
    # Workspace
    # ---------------------------------------------------------

    parser.add_argument(
        "--workspace-mode",
        choices=[
            "last",
            "existing",
            "new",
        ],
        default=None,
    )

    parser.add_argument(
        "--workspace-name",
        type=str,
        default=None,
    )

    # ---------------------------------------------------------
    # Entry
    # ---------------------------------------------------------

    parser.add_argument(
        "--entry-mode",
        choices=[
            "latest",
            "existing",
            "new",
        ],
        default=None,
    )

    parser.add_argument(
        "--entry-name",
        type=str,
        default=None,
    )

    # ---------------------------------------------------------
    # Equipment
    # ---------------------------------------------------------

    parser.add_argument(
        "--equipment",
        choices=[
            "arducam",
            "webcam",
        ],
        default=None,
    )

    # ---------------------------------------------------------
    # Segmentation
    # ---------------------------------------------------------

    parser.add_argument(
        "--segmentation-mode",
        choices=[
            "single",
            "multi",
        ],
        default=None,
    )

    # ---------------------------------------------------------
    # Runtime configuration
    # ---------------------------------------------------------

    handdraw_group = (
        parser.add_mutually_exclusive_group()
    )

    handdraw_group.add_argument(
        "--enable-handdraw",
        dest="enable_handdraw",
        action="store_true",
    )

    handdraw_group.add_argument(
        "--disable-handdraw",
        dest="enable_handdraw",
        action="store_false",
    )

    streaming_group = (
        parser.add_mutually_exclusive_group()
    )

    streaming_group.add_argument(
        "--enable-streaming",
        dest="enable_streaming",
        action="store_true",
    )

    streaming_group.add_argument(
        "--disable-streaming",
        dest="enable_streaming",
        action="store_false",
    )

    preview_group = (
        parser.add_mutually_exclusive_group()
    )

    preview_group.add_argument(
        "--enable-preview",
        dest="enable_preview",
        action="store_true",
    )

    preview_group.add_argument(
        "--disable-preview",
        dest="enable_preview",
        action="store_false",
    )

    synchronization_group = (
        parser.add_mutually_exclusive_group()
    )

    synchronization_group.add_argument(
        "--enable-synchronization",
        dest="enable_synchronization",
        action="store_true",
    )

    synchronization_group.add_argument(
        "--disable-synchronization",
        dest="enable_synchronization",
        action="store_false",
    )

    parser.set_defaults(
        enable_handdraw=ENABLE_HANDDRAW,
        enable_streaming=ENABLE_STREAMING,
        enable_preview=ENABLE_PREVIEW,
        enable_synchronization=ENABLE_SYNCHRONIZATION,
    )

    # ---------------------------------------------------------
    # Optional calibration
    # ---------------------------------------------------------

    parser.add_argument(
        "--intrinsic-file",
        type=Path,
        default=None,
    )

    # ---------------------------------------------------------
    # Parse and validate
    # ---------------------------------------------------------

    args = parser.parse_args(argv)

    if args.workspace_mode in ("existing", "new"):

        if not (
            args.workspace_name
            and args.workspace_name.strip()
        ):

            parser.error(
                "--workspace-name is required "
                "for the selected workspace mode."
            )

    elif args.workspace_name is not None:

        parser.error(
            "--workspace-name requires "
            "--workspace-mode existing or new."
        )

    if args.entry_mode == "existing":

        if not (
            args.entry_name
            and args.entry_name.strip()
        ):

            parser.error(
                "--entry-name is required "
                "when selecting an existing entry."
            )

    elif args.entry_name is not None:

        parser.error(
            "--entry-name requires "
            "--entry-mode existing."
        )

    if (
        args.workspace_mode == "new"
        and args.entry_mode in ("latest", "existing")
    ):

        parser.error(
            "A new workspace requires a new entry."
        )

    if (
        args.enable_synchronization
        and not args.enable_streaming
    ):

        parser.error(
            "Sensing synchronization requires streaming."
        )

    if args.intrinsic_file is not None:

        if not args.intrinsic_file.is_file():

            parser.error(
                f"Intrinsic calibration file not found: "
                f"{args.intrinsic_file}"
            )

    return args


# =============================================================
# MAIN
# =============================================================

def main(
    argv: list[str] | None = None,
) -> None:

    args = parse_arguments(argv)

    entrypoint = EWoodXSensingEntrypointStream(
        equipment=args.equipment,
        segmentation_mode=args.segmentation_mode,

        enable_handdraw=args.enable_handdraw,
        enable_streaming=args.enable_streaming,
        enable_preview=args.enable_preview,

        intrinsic_file=args.intrinsic_file,

        enable_synchronization=(
            args.enable_synchronization
        ),
    )

    entrypoint.run(
        workspace_mode=args.workspace_mode,
        workspace_name=args.workspace_name,

        entry_mode=args.entry_mode,
        entry_name=args.entry_name,
    )


if __name__ == "__main__":
    main()