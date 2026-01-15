from typing import Literal, Any
from pydantic import BaseModel, Field
import logging
import json
from .base import ViktorTool

logger = logging.getLogger(__name__)


class StructuralAnalysisStep1(BaseModel):
    """Step 1 - Geometry parameters"""

    bridge_length: float = Field(default=20000, description="Bridge length in mm")
    bridge_width: float = Field(default=4500, description="Bridge width in mm")
    bridge_height: float = Field(default=3000, description="Bridge height in mm")
    n_divisions: int = Field(default=4, description="Number of divisions")
    cross_section: Literal[
        "HSS200x200x8", "HSS250x250x10", "HSS300x300x12", "HSS350x350x16"
    ] = Field(
        default="HSS200x200x8", description="Cross-section size for bridge members"
    )


class StructuralAnalysisStep2(BaseModel):
    """Step 2 - Loads parameters"""

    load_q: float = Field(default=4, description="Gravitational load Q in kPa")
    wind_pressure: float = Field(default=1.5, description="Wind pressure in kPa")
    wind_cf: float = Field(default=1.6, description="Wind force coefficient Cf")


class StructuralAnalysisInput(BaseModel):
    """Input parameters for structural analysis tool"""

    step_1: StructuralAnalysisStep1 = Field(
        default_factory=StructuralAnalysisStep1, description="Geometry parameters"
    )
    step_2: StructuralAnalysisStep2 = Field(
        default_factory=StructuralAnalysisStep2, description="Load parameters"
    )


class MaxDisplacements(BaseModel):
    dx: float = Field(description="Maximum X displacement in mm")
    dy: float = Field(description="Maximum Y displacement in mm")
    dz: float = Field(description="Maximum Z displacement in mm")


class ModelParameters(BaseModel):
    bridge_length_mm: float
    bridge_width_mm: float
    bridge_height_mm: float
    n_divisions: int
    cross_section: str
    load_q_kPa: float
    wind_pressure_kPa: float


class CombinationResult(BaseModel):
    combination_name: str
    max_abs_displacement_mm: float


class StructuralAnalysisOutput(BaseModel):
    critical_combination: str = Field(
        description="Name of the critical load combination"
    )
    max_displacements_mm: MaxDisplacements = Field(
        description="Maximum displacements in each direction"
    )
    model_parameters: ModelParameters = Field(description="Input model parameters")
    all_combinations_results: list[CombinationResult] = Field(
        description="Results for all load combinations"
    )


class StructuralAnalysisTool(ViktorTool):
    def __init__(
        self,
        structural_input: StructuralAnalysisInput,
        workspace_id: int = 4702,
        entity_id: int = 2437,
        method_name: str = "download_results",
    ):
        super().__init__(workspace_id, entity_id)
        self.structural_input = structural_input
        self.method_name = method_name

    def build_payload(self) -> dict[str, Any]:
        # Decompose params into step keys for VIKTOR parametrization format
        params = {
            "step_1": self.structural_input.step_1.model_dump(),
            "step_2": self.structural_input.step_2.model_dump(),
        }
        return {
            "method_name": self.method_name,
            "params": params,
            "poll_result": True,
        }

    def run_and_download(self) -> dict:
        job = self.run()
        return self.download_result(job)

    def run_and_parse(self) -> StructuralAnalysisOutput:
        content = self.run_and_download()
        return StructuralAnalysisOutput(**content)


async def calculate_structural_analysis_func(ctx: Any, args: str) -> str:
    # Parse flat input and restructure into steps
    raw_input = json.loads(args)

    # Build step_1 from flat input
    step_1_data = {}
    step_1_fields = [
        "bridge_length",
        "bridge_width",
        "bridge_height",
        "n_divisions",
        "cross_section",
    ]
    for field in step_1_fields:
        if field in raw_input:
            step_1_data[field] = raw_input[field]

    # Build step_2 from flat input
    step_2_data = {}
    step_2_fields = ["load_q", "wind_pressure", "wind_cf"]
    for field in step_2_fields:
        if field in raw_input:
            step_2_data[field] = raw_input[field]

    # Create the structured input
    structured_input = {
        "step_1": step_1_data
        if step_1_data
        else StructuralAnalysisStep1().model_dump(),
        "step_2": step_2_data
        if step_2_data
        else StructuralAnalysisStep2().model_dump(),
    }

    payload = StructuralAnalysisInput.model_validate(structured_input)

    tool = StructuralAnalysisTool(structural_input=payload)
    result = tool.run_and_parse()

    max_disp = result.max_displacements_mm
    model_params = result.model_parameters

    result_summary = {
        "critical_combination": result.critical_combination,
        "max_displacement_dx_mm": max_disp.dx,
        "max_displacement_dy_mm": max_disp.dy,
        "max_displacement_dz_mm": max_disp.dz,
        "bridge_length_mm": model_params.bridge_length_mm,
        "bridge_width_mm": model_params.bridge_width_mm,
        "bridge_height_mm": model_params.bridge_height_mm,
        "n_divisions": model_params.n_divisions,
        "cross_section": model_params.cross_section,
        "load_q_kPa": model_params.load_q_kPa,
        "wind_pressure_kPa": model_params.wind_pressure_kPa,
        "all_combinations": [
            {"name": c.combination_name, "max_disp_mm": c.max_abs_displacement_mm}
            for c in result.all_combinations_results
        ],
    }

    return (
        f"Structural analysis completed successfully. "
        f"Critical combination: {result.critical_combination}. "
        f"Max displacements: dx={max_disp.dx}mm, dy={max_disp.dy}mm, dz={max_disp.dz}mm. "
        f"Bridge geometry: L={model_params.bridge_length_mm}mm, W={model_params.bridge_width_mm}mm, H={model_params.bridge_height_mm}mm. "
        f"Cross-section: {model_params.cross_section}. "
        f"Loads: Q={model_params.load_q_kPa}kPa, Wind={model_params.wind_pressure_kPa}kPa. "
        f"Result: {json.dumps(result_summary, indent=2)}"
    )


# Flat input schema for the agent tool (easier for LLM to use)
class StructuralAnalysisFlatInput(BaseModel):
    """Flat input parameters for structural analysis - easier for agent to use"""

    bridge_length: float = Field(default=20000, description="Bridge length in mm")
    bridge_width: float = Field(default=4500, description="Bridge width in mm")
    bridge_height: float = Field(default=3000, description="Bridge height in mm")
    n_divisions: int = Field(default=4, description="Number of divisions")
    cross_section: Literal[
        "HSS200x200x8", "HSS250x250x10", "HSS300x300x12", "HSS350x350x16"
    ] = Field(
        default="HSS200x200x8", description="Cross-section size for bridge members"
    )
    load_q: float = Field(default=4, description="Gravitational load Q in kPa")
    wind_pressure: float = Field(default=1.5, description="Wind pressure in kPa")
    wind_cf: float = Field(default=1.6, description="Wind force coefficient Cf")


def calculate_structural_analysis_tool() -> Any:
    from agents import FunctionTool

    return FunctionTool(
        name="calculate_structural_analysis",
        description=(
            "Run structural analysis on a bridge structure using OpenSees in a Viktor app. "
            "Analyzes the bridge under gravitational and wind loads with multiple SLS load combinations. "
            "Takes geometry parameters (bridge length, width, height, divisions, cross-section) and load parameters (gravitational load Q, wind pressure, wind_cf). "
            "Returns critical load combination, maximum displacements (dx, dy, dz), and results for all combinations. "
            "URL: https://beta.viktor.ai/workspaces/4702/app/editor/2437"
        ),
        params_json_schema=StructuralAnalysisFlatInput.model_json_schema(),
        on_invoke_tool=calculate_structural_analysis_func,
    )


if __name__ == "__main__":
    structural_input = StructuralAnalysisInput(
        step_1=StructuralAnalysisStep1(
            bridge_length=20000,
            bridge_width=4500,
            bridge_height=3000,
            n_divisions=4,
            cross_section="HSS200x200x8",
        ),
        step_2=StructuralAnalysisStep2(
            load_q=4,
            wind_pressure=1.5,
            wind_cf=1.6,
        ),
    )
    tool = StructuralAnalysisTool(structural_input=structural_input)

    result = tool.run_and_parse()

    import pprint

    pprint.pp(result.model_dump())
    print(f"\nCritical combination: {result.critical_combination}")
    print(
        f"Max displacements: dx={result.max_displacements_mm.dx}, dy={result.max_displacements_mm.dy}, dz={result.max_displacements_mm.dz}"
    )
