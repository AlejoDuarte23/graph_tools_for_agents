import json
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, Json

from app.viktor_tools.seismic_load_tool import calculate_seismic_loads_tool
from app.viktor_tools.wind_loads_tool import calculate_wind_loads_tool
from app.viktor_tools.footing_capacity_tool import calculate_footing_capacity_tool
from app.viktor_tools.geometry_tool import generate_geometry_tool
from app.viktor_tools.structural_analysis_tool import calculate_structural_analysis_tool
from app.viktor_tools.sensitivity_analysis_tool import (
    calculate_sensitivity_analysis_tool,
)
from app.viktor_tools.plotting_tool import generate_plot


class Workflow(BaseModel):
    pass


class GeometryGeneration(BaseModel):
    structure_width: float = Field(..., description="Widht of the structure in mm")
    structure_lenght: float = Field(..., description="Lenght of the structure in mm")
    structure_height: float = Field(..., description="Height of the structure in mm")
    csc_section: Literal["UB200x30", "310UBx46"]


class WindloadAnalysis(BaseModel):
    region: Literal["A", "B", "C", "D"]
    wind_speed: float = Field(..., description="Wind speed in m/s")
    exposure_level: Literal["A", "B", "C", "D"]


class SeismicAnalysis(BaseModel):
    soil_cateogory: Literal["A", "B", "C", "D", "F"]
    region: Literal["A", "B", "C", "D"]
    importance_level: Literal["1", "2", "3"]


class Result(BaseModel):
    pass


class StructuralAnalysis(BaseModel):
    geometry_result: Result
    wind_result: Result | None = None
    seismic_result: Result


class FootingCapacity(BaseModel):
    soil_cateogory: Literal["A", "B", "C", "D", "F"]
    foundation_type: Literal["Footing", "Pile", "Slab"]


class FootingDesign(BaseModel):
    reaction_loads: list[float]
    footing_capacity_result: Result


class DummyWorkflowNode(BaseModel):
    node_id: str = Field(..., description="Unique id for this workflow node")
    node_type: Literal[
        "geometry_generation",
        "windload_analysis",
        "seismic_analysis",
        "structural_analysis",
        "footing_capacity",
        "footing_design",
    ] = Field(..., description="Type of workflow node to add to the graph")
    label: str = Field(..., description="Human-readable label for the node")
    url: str | None = Field(
        default=None,
        description="URL to the VIKTOR app tool (optional, falls back to default if not provided)",
    )
    inputs: Json[Any] = Field(
        default="{}",
        description=(
            "Input parameters for the node, provided as a JSON string. "
            'Example: \'{"wind_speed": 45.0, "region": "B"}\'.'
        ),
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="List of upstream node_ids this node depends on",
    )


async def create_dummy_workflow_node_func(
    _ctx: Any,
    args: str,
) -> str:
    payload = DummyWorkflowNode.model_validate_json(args)
    return f"Node '{payload.node_id}' ({payload.node_type}) created successfully."


def create_dummy_workflow_node_tool() -> Any:
    from agents import FunctionTool

    return FunctionTool(
        name="create_dummy_workflow_node",
        description="Create a dummy workflow-node JSON artifact for graph composition.",
        params_json_schema=DummyWorkflowNode.model_json_schema(),
        on_invoke_tool=create_dummy_workflow_node_func,
    )


class ComposeWorkflowGraphArgs(BaseModel):
    workflow_name: Annotated[str, Field(description="Name for the composed workflow")]
    nodes: Annotated[
        list[DummyWorkflowNode],
        Field(description="Workflow nodes with dependencies to compose"),
    ]
    output_dir: Annotated[
        str,
        Field(description="Directory (relative to cwd) where artifacts are written"),
    ] = "workflow_graph/generated_workflows"
    write_workflow_json: Annotated[
        bool, Field(description="Also write a `workflow.json` artifact")
    ] = True


def toposort_edges(nodes: list[str], edges: list[tuple[str, str]]) -> bool:
    indegree: dict[str, int] = {n: 0 for n in nodes}
    outgoing: dict[str, list[str]] = {n: [] for n in nodes}
    for src, dst in edges:
        outgoing.setdefault(src, []).append(dst)
        indegree[dst] = indegree.get(dst, 0) + 1

    queue = [n for n, deg in indegree.items() if deg == 0]
    visited = 0
    while queue:
        node = queue.pop()
        visited += 1
        for nxt in outgoing.get(node, []):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    return visited == len(nodes)


async def compose_workflow_graph_func(ctx: Any, args: str) -> str:
    payload = ComposeWorkflowGraphArgs.model_validate_json(args)

    ids = [n.node_id for n in payload.nodes]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"Duplicate node_id(s): {', '.join(duplicates)}")

    id_set = set(ids)
    missing_deps: dict[str, list[str]] = {}
    edges: list[tuple[str, str]] = []
    for n in payload.nodes:
        unknown = [d for d in n.depends_on if d not in id_set]
        if unknown:
            missing_deps[n.node_id] = unknown
        for d in n.depends_on:
            edges.append((d, n.node_id))
    if missing_deps:
        msg = "; ".join(
            f"{nid} -> missing {', '.join(deps)}" for nid, deps in missing_deps.items()
        )
        raise ValueError(f"Unknown dependency node_id(s): {msg}")

    if not toposort_edges(ids, edges):
        raise ValueError("Cycle detected in depends_on; workflow_graph expects a DAG.")

    from app.workflow_graph.models import Connection, Node, Workflow
    from app.workflow_graph.viewer import WorkflowViewer

    # Default fallback URL
    default_url = "https://beta.viktor.ai/workspaces/4672/app/editor/2394"

    workflow = Workflow(
        nodes=[
            Node(
                id=n.node_id,
                title=n.label,
                type=n.node_type,
                url=n.url or default_url,
                depends_on=[Connection(node_id=d) for d in n.depends_on],
            )
            for n in payload.nodes
        ]
    )

    viewer = WorkflowViewer(
        lambda: workflow,
        root_dir=Path(__file__).resolve().parent / "workflow_graph",
    )
    html_content = viewer.write()  # Returns HTML string

    # Store HTML in VIKTOR storage for WebView access
    try:
        import viktor as vkt

        data_json = json.dumps(
            {
                "html": html_content,
                "workflow_name": payload.workflow_name,
            }
        )
        vkt.Storage().set(
            "workflow_html",
            data=vkt.File.from_data(data_json),
            scope="entity",
        )
    except Exception:
        # Ignore if not running in VIKTOR context
        pass

    # Optionally write workflow JSON for debugging
    json_path: Path | None = None
    if payload.write_workflow_json:
        out_dir = Path.cwd() / payload.output_dir / payload.workflow_name
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path = out_dir / "workflow.json"
        json_path.write_text(
            json.dumps(workflow.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return f"Workflow '{payload.workflow_name}' created successfully with {len(payload.nodes)} nodes and {len(edges)} connections. The workflow graph has been updated and is now visible in the Workflow Graph view on the right side."


def compose_workflow_graph_tool() -> Any:
    from agents import FunctionTool

    return FunctionTool(
        name="compose_workflow_graph",
        description="Compose nodes into a workflow_graph DAG and render a self-contained HTML graph.",
        params_json_schema=ComposeWorkflowGraphArgs.model_json_schema(),
        on_invoke_tool=compose_workflow_graph_func,
    )


def get_tools() -> list[Any]:
    return [
        create_dummy_workflow_node_tool(),
        compose_workflow_graph_tool(),
        calculate_seismic_loads_tool(),
        calculate_wind_loads_tool(),
        calculate_footing_capacity_tool(),
        generate_geometry_tool(),
        calculate_structural_analysis_tool(),
        calculate_sensitivity_analysis_tool(),
        generate_plot(),
    ]
