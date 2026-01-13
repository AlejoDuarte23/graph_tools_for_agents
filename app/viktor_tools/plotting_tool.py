import viktor as vkt
from pydantic import BaseModel, Field
from typing import Any


class PlotTool(BaseModel):
    """Arguments for a bar-plot tool"""

    x: list[float] = Field(..., description="X-axis values")
    y: list[float] = Field(..., description="Y-axis values")


async def display_dashboard_func(ctx: Any, args: str) -> str | None:
    """Displays Plot in plotly"""

    payload = PlotTool.model_validate_json(args)

    if payload:
        vkt.Storage().set(
            "PlotTool",
            data=vkt.File.from_data(payload.model_dump_json()),
            scope="entity",
        )
        return "Plotly Graph generated. Open the Model Viewer panel to view it."
    return f"Validation error Incorrect Outputs {args}"


def generate_plot() -> Any:
    from agents import FunctionTool

    return FunctionTool(
        name="generate_plotly",
        description=(
            "Generate a Plotly bar plot visualization. "
            "Takes x-axis and y-axis values as lists of floats. "
            "The plot will be displayed in the Plot view panel."
        ),
        params_json_schema=PlotTool.model_json_schema(),
        on_invoke_tool=display_dashboard_func,
    )
