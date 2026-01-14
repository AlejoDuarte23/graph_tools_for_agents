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
    truss_length_mm: float
    truss_width_mm: float
    truss_height_mm: float
    n_divisions: int
    cross_section_mm: float


class Model(BaseModel):
    parameters: Parameters
    metadata: Metadata


class GeometryGeneration(BaseModel):
    truss_length: float = Field(default=10000, description="Truss length in mm")
    truss_width: float = Field(default=1100, description="Truss width in mm")
    truss_height: float = Field(default=1500, description="Truss height in mm")
    n_divisions: int = Field(default=8, description="Number of divisions")
    cross_section: Literal["SHS50x4", "SHS75x4", "SHS100x4", "SHS150x4"] = Field(
        default="SHS100x4", description="Cross-section size for truss members"
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
        "truss_length": payload.truss_length,
        "truss_width": payload.truss_width,
        "truss_height": payload.truss_height,
        "n_divisions": payload.n_divisions,
        "cross_section": payload.cross_section,
    }

    return (
        f"Truss geometry generated successfully with {nodes_count} nodes and "
        f"{lines_count} lines. "
        f"Truss dimensions: {payload.truss_length}mm x {payload.truss_width}mm x {payload.truss_height}mm. "
        f"Divisions: {payload.n_divisions}, Cross-section: {payload.cross_section}. "
        f"Result: {json.dumps(result_summary, indent=2)}"
    )


def generate_geometry_tool() -> Any:
    from agents import FunctionTool

    return FunctionTool(
        name="generate_geometry",
        description=(
            "Generate 3D rectangular truss beam geometry in a VIKTOR app (nodes, lines, members). "
            "Parameters: truss_length, truss_width, truss_height (all in mm), n_divisions (number of truss divisions), "
            "and cross_section (SHS50x4, SHS75x4, SHS100x4, or SHS150x4). "
            "Returns a structural model with nodes (3D coordinates) and lines (connections between nodes)."
        ),
        params_json_schema=GeometryGeneration.model_json_schema(),
        on_invoke_tool=generate_geometry_func,
    )


if __name__ == "__main__":
    import pprint

    geometry = GeometryGeneration(
        truss_length=10000,
        truss_width=1000,
        truss_height=1500,
        n_divisions=6,
        cross_section="SHS100x4",
    )
    tool = GeometryGenerationTool(geometry=geometry)

    # First, let's see the raw JSON structure
    content = tool.run_and_download()
    print("=== Raw response keys ===")
    pprint.pp(list(content.keys()))
    print("\n=== Full response structure ===")
    pprint.pp(content)
