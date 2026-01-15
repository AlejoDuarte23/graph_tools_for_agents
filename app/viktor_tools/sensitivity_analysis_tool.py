from typing import Literal, Any
from pydantic import BaseModel, Field
import logging
import json
from .base import ViktorTool

logger = logging.getLogger(__name__)


class SensitivityAnalysisStep1(BaseModel):
    """Step 1 - Geometry parameters"""

    bridge_length: float = Field(default=20000, description="Bridge length in mm")
    bridge_width: float = Field(default=4500, description="Bridge width in mm")
    n_divisions: int = Field(default=4, description="Number of divisions")
    cross_section: Literal[
        "HSS200x200x8", "HSS250x250x10", "HSS300x300x12", "HSS350x350x16"
    ] = Field(
        default="HSS200x200x8", description="Cross-section size for bridge members"
    )


class SensitivityAnalysisStep2(BaseModel):
    """Step 2 - Loads parameters"""

    load_q: float = Field(default=4, description="Gravitational load Q in kPa")
    wind_pressure: float = Field(default=1.5, description="Wind pressure in kPa")


class SensitivityAnalysisStep4(BaseModel):
    """Step 4 - Sensitivity Analysis parameters"""

    min_height: float = Field(default=1000, description="Minimum bridge height in mm")
    max_height: float = Field(default=7000, description="Maximum bridge height in mm")
    n_steps: int = Field(
        default=10, description="Number of steps for sensitivity analysis"
    )


class SensitivityAnalysisInput(BaseModel):
    """Input parameters for sensitivity analysis tool"""

    step_1: SensitivityAnalysisStep1 = Field(
        default_factory=SensitivityAnalysisStep1, description="Geometry parameters"
    )
    step_2: SensitivityAnalysisStep2 = Field(
        default_factory=SensitivityAnalysisStep2, description="Load parameters"
    )
    step_4: SensitivityAnalysisStep4 = Field(
        default_factory=SensitivityAnalysisStep4,
        description="Sensitivity analysis parameters",
    )


class SensitivityDataPoint(BaseModel):
    height_mm: float = Field(description="Bridge height in mm")
    max_dz_mm: float = Field(description="Maximum Z displacement in mm")
    critical_combination: str = Field(
        description="Name of the critical load combination"
    )


class SensitivityModelParameters(BaseModel):
    bridge_length_mm: float
    bridge_width_mm: float
    min_height_mm: float
    max_height_mm: float
    n_steps: int
    n_divisions: int
    cross_section: str
    load_q_kPa: float
    wind_pressure_kPa: float


class SensitivityAnalysisOutput(BaseModel):
    sensitivity_analysis: list[SensitivityDataPoint] = Field(
        description="List of sensitivity analysis data points"
    )
    model_parameters: SensitivityModelParameters = Field(
        description="Input model parameters for sensitivity analysis"
    )


class SensitivityAnalysisTool(ViktorTool):
    def __init__(
        self,
        sensitivity_input: SensitivityAnalysisInput,
        workspace_id: int = 4702,
        entity_id: int = 2437,
        method_name: str = "download_sensitivity_results",
    ):
        super().__init__(workspace_id, entity_id)
        self.sensitivity_input = sensitivity_input
        self.method_name = method_name

    def build_payload(self) -> dict[str, Any]:
        # Decompose params into step keys for VIKTOR parametrization format
        params = {
            "step_1": self.sensitivity_input.step_1.model_dump(),
            "step_2": self.sensitivity_input.step_2.model_dump(),
            "step_4": self.sensitivity_input.step_4.model_dump(),
        }
        return {
            "method_name": self.method_name,
            "params": params,
            "poll_result": True,
        }

    def run_and_download(self) -> dict:
        job = self.run()
        return self.download_result(job)

    def run_and_parse(self) -> SensitivityAnalysisOutput:
        content = self.run_and_download()
        return SensitivityAnalysisOutput(**content)


async def calculate_sensitivity_analysis_func(ctx: Any, args: str) -> str:
    # Parse flat input and restructure into steps
    raw_input = json.loads(args)

    # Build step_1 from flat input
    step_1_data = {}
    step_1_fields = [
        "bridge_length",
        "bridge_width",
        "n_divisions",
        "cross_section",
    ]
    for field in step_1_fields:
        if field in raw_input:
            step_1_data[field] = raw_input[field]

    # Build step_2 from flat input
    step_2_data = {}
    step_2_fields = ["load_q", "wind_pressure"]
    for field in step_2_fields:
        if field in raw_input:
            step_2_data[field] = raw_input[field]

    # Build step_4 from flat input
    step_4_data = {}
    step_4_fields = ["min_height", "max_height", "n_steps"]
    for field in step_4_fields:
        if field in raw_input:
            step_4_data[field] = raw_input[field]

    # Create the structured input
    structured_input = {
        "step_1": step_1_data
        if step_1_data
        else SensitivityAnalysisStep1().model_dump(),
        "step_2": step_2_data
        if step_2_data
        else SensitivityAnalysisStep2().model_dump(),
        "step_4": step_4_data
        if step_4_data
        else SensitivityAnalysisStep4().model_dump(),
    }

    payload = SensitivityAnalysisInput.model_validate(structured_input)

    tool = SensitivityAnalysisTool(sensitivity_input=payload)
    result = tool.run_and_parse()

    model_params = result.model_parameters
    sensitivity_data = result.sensitivity_analysis

    # Find min and max deformation points
    min_deform = min(sensitivity_data, key=lambda x: x.max_dz_mm)
    max_deform = max(sensitivity_data, key=lambda x: x.max_dz_mm)

    result_summary = {
        "bridge_length_mm": model_params.bridge_length_mm,
        "bridge_width_mm": model_params.bridge_width_mm,
        "min_height_mm": model_params.min_height_mm,
        "max_height_mm": model_params.max_height_mm,
        "n_steps": model_params.n_steps,
        "n_divisions": model_params.n_divisions,
        "cross_section": model_params.cross_section,
        "load_q_kPa": model_params.load_q_kPa,
        "wind_pressure_kPa": model_params.wind_pressure_kPa,
        "min_deformation": {
            "height_mm": min_deform.height_mm,
            "max_dz_mm": min_deform.max_dz_mm,
        },
        "max_deformation": {
            "height_mm": max_deform.height_mm,
            "max_dz_mm": max_deform.max_dz_mm,
        },
        "all_data_points": [
            {
                "height_mm": d.height_mm,
                "max_dz_mm": d.max_dz_mm,
                "critical_combination": d.critical_combination,
            }
            for d in sensitivity_data
        ],
    }

    return (
        f"Sensitivity analysis completed successfully. "
        f"Analyzed {len(sensitivity_data)} height variations from {model_params.min_height_mm}mm to {model_params.max_height_mm}mm. "
        f"Minimum deformation: {min_deform.max_dz_mm}mm at height {min_deform.height_mm}mm. "
        f"Maximum deformation: {max_deform.max_dz_mm}mm at height {max_deform.height_mm}mm. "
        f"Bridge geometry: L={model_params.bridge_length_mm}mm, W={model_params.bridge_width_mm}mm. "
        f"Cross-section: {model_params.cross_section}. "
        f"Loads: Q={model_params.load_q_kPa}kPa, Wind={model_params.wind_pressure_kPa}kPa. "
        f"Result: {json.dumps(result_summary, indent=2)}"
    )


# Flat input schema for the agent tool (easier for LLM to use)
class SensitivityAnalysisFlatInput(BaseModel):
    """Flat input parameters for sensitivity analysis - easier for agent to use"""

    bridge_length: float = Field(default=20000, description="Bridge length in mm")
    bridge_width: float = Field(default=4500, description="Bridge width in mm")
    n_divisions: int = Field(default=4, description="Number of divisions")
    cross_section: Literal[
        "HSS200x200x8", "HSS250x250x10", "HSS300x300x12", "HSS350x350x16"
    ] = Field(
        default="HSS200x200x8", description="Cross-section size for bridge members"
    )
    load_q: float = Field(default=4, description="Gravitational load Q in kPa")
    wind_pressure: float = Field(default=1.5, description="Wind pressure in kPa")
    min_height: float = Field(
        default=1000, description="Minimum bridge height in mm for sensitivity analysis"
    )
    max_height: float = Field(
        default=7000, description="Maximum bridge height in mm for sensitivity analysis"
    )
    n_steps: int = Field(
        default=10, description="Number of steps for sensitivity analysis"
    )


def calculate_sensitivity_analysis_tool() -> Any:
    from agents import FunctionTool

    return FunctionTool(
        name="calculate_sensitivity_analysis",
        description=(
            "Run sensitivity analysis on a bridge structure varying the bridge height using OpenSees in a Viktor app. "
            "Analyzes how bridge depth (height) affects the maximum vertical deformation under gravitational and wind loads. "
            "Takes geometry parameters (bridge length, width, divisions, cross-section), load parameters (gravitational load Q, wind pressure), "
            "and sensitivity parameters (min_height, max_height, n_steps). "
            "Returns deformation data for each height value, identifying optimal bridge height for minimum deflection. "
            "URL: https://beta.viktor.ai/workspaces/4702/app/editor/2437"
        ),
        params_json_schema=SensitivityAnalysisFlatInput.model_json_schema(),
        on_invoke_tool=calculate_sensitivity_analysis_func,
    )


if __name__ == "__main__":
    sensitivity_input = SensitivityAnalysisInput(
        step_1=SensitivityAnalysisStep1(
            bridge_length=20000,
            bridge_width=4500,
            n_divisions=4,
            cross_section="HSS200x200x8",
        ),
        step_2=SensitivityAnalysisStep2(
            load_q=4,
            wind_pressure=1.5,
        ),
        step_4=SensitivityAnalysisStep4(
            min_height=1000,
            max_height=7000,
            n_steps=10,
        ),
    )
    tool = SensitivityAnalysisTool(sensitivity_input=sensitivity_input)

    result = tool.run_and_parse()

    import pprint

    pprint.pp(result.model_dump())
    print(f"\nAnalyzed {len(result.sensitivity_analysis)} data points")
