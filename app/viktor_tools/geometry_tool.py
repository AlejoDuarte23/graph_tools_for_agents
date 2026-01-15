from typing import Literal, Any
from pydantic import BaseModel, Field
import logging
import json
from .base import ViktorTool

logger = logging.getLogger(__name__)


class Metadata(BaseModel):
    total_nodes: int
    total_lines: int
    units: dict[str, str]


class Parameters(BaseModel):
    bridge_length_mm: float
    bridge_width_mm: float
    bridge_height_mm: float
    n_divisions: int
    cross_section_mm: float


class Model(BaseModel):
    parameters: Parameters
    metadata: Metadata


class GeometryGeneration(BaseModel):
    bridge_length: float = Field(default=20000, description="Bridge length in mm")
    bridge_width: float = Field(default=4500, description="Bridge width in mm")
    bridge_height: float = Field(default=3000, description="Bridge height in mm")
    n_divisions: int = Field(default=4, description="Number of divisions")
    cross_section: Literal[
        "HSS200×200×8", "HSS250×250×10", "HSS300×300×12", "HSS350×350×16"
    ] = Field(
        default="HSS200×200×8", description="Cross-section size for bridge members"
    )


class GeometryGenerationTool(ViktorTool):
    def __init__(
        self,
        geometry: GeometryGeneration,
        workspace_id: int = 4704,
        entity_id: int = 2447,
        method_name: str = "download_geometry_json",
    ):
        super().__init__(workspace_id, entity_id)
        self.geometry = geometry
        self.method_name = method_name

    def build_payload(self) -> dict[str, Any]:
        return {
            "method_name": self.method_name,
            "params": self.geometry.model_dump(),
            "poll_result": False,
        }

    def run_and_download(self) -> dict:
        job = self.run()
        return self.download_result(job)

    def run_and_parse(self) -> Model:
        content = self.run_and_download()
        # Debug: print the actual structure
        logger.info(f"Response keys: {content.keys()}")
        return Model(**content)


async def generate_geometry_func(ctx: Any, args: str) -> str:
    payload = GeometryGeneration.model_validate_json(args)

    tool = GeometryGenerationTool(geometry=payload)
    model = tool.run_and_parse()

    nodes_count = model.metadata.total_nodes
    lines_count = model.metadata.total_lines

    result_summary = {
        "nodes": nodes_count,
        "lines": lines_count,
        "bridge_length": payload.bridge_length,
        "bridge_width": payload.bridge_width,
        "bridge_height": payload.bridge_height,
        "n_divisions": payload.n_divisions,
        "cross_section": payload.cross_section,
    }

    return (
        f"Bridge geometry generated successfully with {nodes_count} nodes and "
        f"{lines_count} lines. "
        f"Bridge dimensions: {payload.bridge_length}mm x {payload.bridge_width}mm x {payload.bridge_height}mm. "
        f"Divisions: {payload.n_divisions}, Cross-section: {payload.cross_section}. "
        f"Result: {json.dumps(result_summary, indent=2)}"
    )


def generate_geometry_tool() -> Any:
    from agents import FunctionTool

    return FunctionTool(
        name="generate_geometry",
        description=(
            "Generate 3D parametric truss bridge geometry in a VIKTOR app (nodes, lines, members). "
            "Parameters: bridge_length, bridge_width, bridge_height (all in mm), n_divisions (number of bridge divisions), "
            "and cross_section (HSS200×200×8, HSS250×250×10, HSS300×300×12, or HSS350×350×16). "
            "Returns a structural model with nodes (3D coordinates) and lines (connections between nodes)."
        ),
        params_json_schema=GeometryGeneration.model_json_schema(),
        on_invoke_tool=generate_geometry_func,
    )


if __name__ == "__main__":
    import pprint

    geometry = GeometryGeneration(
        bridge_length=20000,
        bridge_width=4500,
        bridge_height=3000,
        n_divisions=4,
        cross_section="HSS200×200×8",
    )
    tool = GeometryGenerationTool(geometry=geometry)

    # First, let's see the raw JSON structure
    content = tool.run_and_download()
    print("=== Raw response keys ===")
    pprint.pp(list(content.keys()))
    print("\n=== Full response structure ===")
    pprint.pp(content)
