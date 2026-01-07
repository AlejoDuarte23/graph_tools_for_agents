from typing import Literal, Any
from pydantic import BaseModel, Field
import requests
import logging
import json
from .base import ViktorTool

logger = logging.getLogger(__name__)


class Node(BaseModel):
    x: float
    y: float
    z: float


class Line(BaseModel):
    start: int | str
    end: int | str


class Member(BaseModel):
    member_id: int | str
    cross_section: str


class Model(BaseModel):
    nodes: dict[str, Node]
    lines: dict[str, Line]
    members: dict[str, Member]


class GeometryGeneration(BaseModel):
    structure_width: float = Field(..., description="Width of the structure in mm")
    structure_length: float = Field(..., description="Length of the structure in mm")
    structure_height: float = Field(..., description="Height of the structure in mm")
    csc_section: Literal["UB200x30", "310UBx46"] = Field(
        ..., description="Cross-section type"
    )


class GeometryGenerationTool(ViktorTool):
    def __init__(
        self,
        geometry: GeometryGeneration,
        workspace_id: int = 4672,
        entity_id: int = 2394,
        method_name: str = "download_model_json",
    ):
        super().__init__(workspace_id, entity_id)
        self.geometry = geometry
        self.method_name = method_name

    def build_payload(self) -> dict[str, Any]:
        return {
            "method_name": self.method_name,
            "params": self.geometry.model_dump(),
            "poll_result": True,
        }

    def download_result(self, result: dict) -> dict:
        if "url" not in result:
            raise ValueError("No URL in result to download")

        download_url = result["url"]
        logger.info(f"Downloading result from {download_url}")

        response = requests.get(download_url)
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to download result (status={response.status_code}): {response.text[:500]}"
            )

        return response.json()

    def run_and_download(self) -> dict:
        result = self.run()
        return self.download_result(result)

    def run_and_parse(self) -> Model:
        content = self.run_and_download()
        return Model(**content)


async def generate_geometry_func(ctx: Any, args: str) -> str:
    payload = GeometryGeneration.model_validate_json(args)

    tool = GeometryGenerationTool(geometry=payload)
    model = tool.run_and_parse()

    nodes_count = len(model.nodes)
    lines_count = len(model.lines)
    members_count = len(model.members)

    result_summary = {
        "nodes": nodes_count,
        "lines": lines_count,
        "members": members_count,
        "structure_width": payload.structure_width,
        "structure_length": payload.structure_length,
        "structure_height": payload.structure_height,
        "csc_section": payload.csc_section,
    }

    return (
        f"Geometry generated successfully with {nodes_count} nodes, "
        f"{lines_count} lines, and {members_count} members. "
        f"Structure dimensions: {payload.structure_width}mm x {payload.structure_length}mm x {payload.structure_height}mm. "
        f"Cross-section: {payload.csc_section}. "
        f"Result: {json.dumps(result_summary, indent=2)}"
    )


def generate_geometry_tool() -> Any:
    from agents import FunctionTool

    return FunctionTool(
        name="generate_geometry",
        description=(
            "Generate 3D structural geometry in a viktor app (nodes, lines, members) based on width, length, height, and cross-section. "
            "Returns a structural model with nodes (3D coordinates), lines (connections between nodes), "
            "and members (structural elements with assigned cross-sections)."
        ),
        params_json_schema=GeometryGeneration.model_json_schema(),
        on_invoke_tool=generate_geometry_func,
    )


if __name__ == "__main__":
    geometry = GeometryGeneration(
        structure_height=3000,
        structure_width=5000,
        structure_length=5000,
        csc_section="UB200x30",
    )
    tool = GeometryGenerationTool(geometry=geometry)

    # Download the actual JSON content
    model = tool.run_and_parse()

    import pprint

    pprint.pp(model)
