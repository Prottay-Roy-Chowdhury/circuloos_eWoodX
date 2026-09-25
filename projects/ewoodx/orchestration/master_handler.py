"""eWoodX master-side orchestration request handling."""

from typing import Any, Dict

from framework.workspace import (
    DomainManager,
    EntityManager,
    EntryManager,
    load_workspace,
)

from projects.ewoodx.config import (
    EWOODX_REPOSITORY_ROOT,
    EWOODX_WORKSPACE_LAYOUT,
    TIMBER_ENTITY_INDEX,
)

from framework.communication.workflow import (
    WorkflowHandler,
)

from framework.orchestration import (
    Orchestrator,
)

from projects.ewoodx.orchestration.definitions import (
    SENSING_ORCHESTRATION,
)


class EWoodXMasterHandler:
    """
    Compose eWoodX orchestration requests with the
    generic distributed workflow handler.
    """

    def __init__(
        self,
        workflow_handler: WorkflowHandler,
        orchestrator: Orchestrator,
    ):
        if not isinstance(
            workflow_handler,
            WorkflowHandler,
        ):
            raise TypeError(
                "workflow_handler must be a WorkflowHandler."
            )

        if not isinstance(
            orchestrator,
            Orchestrator,
        ):
            raise TypeError(
                "orchestrator must be an Orchestrator."
            )

        self.workflow_handler = workflow_handler
        self.orchestrator = orchestrator

    def handle(
        self,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle project orchestration requests and delegate
        generic workflow requests to WorkflowHandler.
        """

        if not isinstance(
            request,
            dict,
        ):
            raise TypeError(
                "request must be a dictionary."
            )

        command = str(
            request.get(
                "command",
                "",
            )
        ).strip().lower()

        if command == "list_workspaces":
            return self._list_workspaces()

        if command == "list_indexed_entries":
            return self._list_indexed_entries(
                request
            )

        if command == "query_entities":
            return self._query_entities(
                request
            )

        if command == "start_orchestration":
            return self._start_orchestration(
                request
            )

        return self.workflow_handler.handle(
            request
        )

    def _start_orchestration(
        self,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        orchestration_name = str(
            request.get(
                "orchestration",
                "",
            )
        ).strip().lower()

        if not orchestration_name:
            return {
                "status": "error",
                "message": "Missing orchestration.",
            }

        if orchestration_name != "sensing":
            return {
                "status": "error",
                "message": (
                    "Unknown eWoodX orchestration: "
                    f"{orchestration_name}"
                ),
            }

        try:
            action = self.orchestrator.start(
                definition=SENSING_ORCHESTRATION,
            )

            return {
                "status": "ok",
                "orchestration": orchestration_name,
                "action": action.to_dict(),
            }

        except Exception as error:
            return {
                "status": "error",
                "message": str(
                    error
                ),
            }

    def _list_workspaces(
        self,
    ) -> Dict[str, Any]:
        try:
            workspaces_root = (
                EWOODX_REPOSITORY_ROOT
                / "workspaces"
            )

            if not workspaces_root.is_dir():
                return {
                    "status": "ok",
                    "workspaces": [],
                }

            workspaces = []

            for path in sorted(
                workspaces_root.iterdir()
            ):
                if (
                    path.is_dir()
                    and (
                        path
                        / "workspace.json"
                    ).is_file()
                ):
                    workspaces.append(
                        path.name
                    )

            return {
                "status": "ok",
                "workspaces": workspaces,
            }

        except Exception as error:
            return {
                "status": "error",
                "message": str(error),
            }


    def _load_workspace_entity_manager(
        self,
        workspace_name: str,
    ) -> EntityManager:
        workspace_name = str(
            workspace_name or ""
        ).strip()

        if not workspace_name:
            raise ValueError(
                "Missing workspace."
            )

        workspace = load_workspace(
            project_root=EWOODX_REPOSITORY_ROOT,
            workspace_name=workspace_name,
            layout=EWOODX_WORKSPACE_LAYOUT,
        )

        domain_manager = DomainManager(
            workspace=workspace,
        )

        # EntityManager is workspace-wide for querying,
        # but its constructor requires one valid EntryPaths.
        # Reuse the first existing managed entry only as
        # construction context. No entity query is scoped
        # to this entry.
        for domain in domain_manager.list_domains():

            entry_manager = EntryManager(
                domain=domain,
            )

            entries = (
                entry_manager.list_entries()
            )

            if entries:
                return EntityManager(
                    workspace=workspace,
                    entry=entries[0],
                    index_schema=TIMBER_ENTITY_INDEX,
                )

        raise FileNotFoundError(
            "No managed entries found in workspace: "
            f"{workspace_name}"
        )

    def _entity_location(
        self,
        entity_manager: EntityManager,
        entity,
    ) -> Dict[str, str]:

        relative_path = (
            entity.root
            .relative_to(
                entity_manager.workspace.root
            )
        )

        parts = relative_path.parts

        if len(parts) < 3:
            raise ValueError(
                "Entity path does not match the "
                "expected domain/entry/entity hierarchy: "
                f"{relative_path}"
            )

        return {
            "domain": parts[0],
            "entry": parts[1],
        }

    def _list_indexed_entries(
        self,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            workspace_name = str(
                request.get(
                    "workspace",
                    "",
                )
            ).strip()

            entity_manager = (
                self._load_workspace_entity_manager(
                    workspace_name
                )
            )

            entities = (
                entity_manager.query_entities()
            )

            counts = {}

            for entity in entities:

                location = (
                    self._entity_location(
                        entity_manager,
                        entity,
                    )
                )

                key = (
                    location["domain"],
                    location["entry"],
                )

                counts[key] = (
                    counts.get(key, 0)
                    + 1
                )

            entries = [
                {
                    "domain": domain,
                    "entry": entry,
                    "entity_count": count,
                }
                for (
                    domain,
                    entry,
                ), count in sorted(
                    counts.items()
                )
            ]

            return {
                "status": "ok",
                "workspace": workspace_name,
                "entries": entries,
            }

        except Exception as error:
            return {
                "status": "error",
                "message": str(error),
            }

    def _query_entities(
        self,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            workspace_name = str(
                request.get(
                    "workspace",
                    "",
                )
            ).strip()

            filters = request.get(
                "filters",
                {},
            )

            selected_entries = request.get(
                "entries",
                None,
            )

            if selected_entries is not None:
                if not isinstance(
                    selected_entries,
                    list,
                ):
                    raise TypeError(
                        "entries must be a list."
                    )

            entity_manager = (
                self._load_workspace_entity_manager(
                    workspace_name
                )
            )

            # Existing generic database query.
            entities = (
                entity_manager.query_entities(
                    filters=filters,
                )
            )

            selected_keys = None

            if selected_entries:
                selected_keys = set()

                for item in selected_entries:

                    if not isinstance(
                        item,
                        dict,
                    ):
                        raise TypeError(
                            "Each entry selection must "
                            "be a dictionary."
                        )

                    domain = str(
                        item.get(
                            "domain",
                            "",
                        )
                    ).strip()

                    entry = str(
                        item.get(
                            "entry",
                            "",
                        )
                    ).strip()

                    if (
                        not domain
                        or not entry
                    ):
                        raise ValueError(
                            "Each entry selection requires "
                            "'domain' and 'entry'."
                        )

                    selected_keys.add(
                        (
                            domain,
                            entry,
                        )
                    )

            results = []

            for entity in entities:

                location = (
                    self._entity_location(
                        entity_manager,
                        entity,
                    )
                )

                location_key = (
                    location["domain"],
                    location["entry"],
                )

                if (
                    selected_keys is not None
                    and location_key
                    not in selected_keys
                ):
                    continue

                results.append(
                    {
                        "entity_id": (
                            entity.entity_id
                        ),
                        "domain": (
                            location["domain"]
                        ),
                        "entry": (
                            location["entry"]
                        ),
                    }
                )

            return {
                "status": "ok",
                "workspace": workspace_name,
                "count": len(results),
                "entities": results,
            }

        except Exception as error:
            return {
                "status": "error",
                "message": str(error),
            }