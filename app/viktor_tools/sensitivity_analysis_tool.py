from typing import Literal, Any
from pydantic import BaseModel, Field
import requests
import logging
import json
from .base import ViktorTool

logger = logging.getLogger(__name__)


class SensitivityAnalysisStep1(BaseModel):
    """Step 1 - Geometry parameters"""

    truss_length: float = Field(default=10000, description="Truss length in mm")
    truss_width: float = Field(default=1000, description="Truss width in mm")
    n_divisions: int = Field(default=6, description="Number of divisions")
    cross_section: Literal["SHS50x4", "SHS75x4", "SHS100x4", "SHS150x4"] = Field(
        default="SHS100x4", description="Cross-section size for truss members"
    )


class SensitivityAnalysisStep2(BaseModel):
    """Step 2 - Loads parameters"""

    load_q: float = Field(default=5, description="Gravitational load Q in kPa")
    wind_pressure: float = Field(default=1, description="Wind pressure in kPa")


class SensitivityAnalysisStep4(BaseModel):
    """Step 4 - Sensitivity Analysis parameters"""

    min_height: float = Field(default=500, description="Minimum truss height in mm")
    max_height: float = Field(default=3000, description="Maximum truss height in mm")
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
    height_mm: float = Field(description="Truss height in mm")
    max_dz_mm: float = Field(description="Maximum Z displacement in mm")
    critical_combination: str = Field(
        description="Name of the critical load combination"
    )


class SensitivityModelParameters(BaseModel):
    truss_length_mm: float
    truss_width_mm: float
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

    def download_result(self, result: dict) -> dict:
        # If the job already returned the JSON content, return it directly.
        if "sensitivity_analysis" in result and "model_parameters" in result:
            return result

        # Check for download URL (may be under 'url' or 'download')
        download_url = result.get("url") or result.get("download")
        if not download_url:
            raise ValueError(
                f"No URL in result to download. Keys={list(result.keys())}"
            )

        # Handle nested dict structure {'url': '...'}
        if isinstance(download_url, dict):
            download_url = download_url.get("url")
        if not download_url:
            raise ValueError(f"Could not extract download URL from result: {result}")

        logger.info(f"Downloading result from {download_url}")

        response = requests.get(
            download_url,
            timeout=(5, 120),
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to download result (status={response.status_code}): {response.text[:500]}"
            )

        return response.json()

    def run_and_download(self) -> dict:
        result = self.run()
        return self.download_result(result)

    def run_and_parse(self) -> SensitivityAnalysisOutput:
        content = self.run_and_download()
        return SensitivityAnalysisOutput(**content)


async def calculate_sensitivity_analysis_func(ctx: Any, args: str) -> str:
    # Parse flat input and restructure into steps
    raw_input = json.loads(args)

    # Build step_1 from flat input
    step_1_data = {}
    step_1_fields = [
        "truss_length",
        "truss_width",
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
        "truss_length_mm": model_params.truss_length_mm,
        "truss_width_mm": model_params.truss_width_mm,
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
        f"Truss geometry: L={model_params.truss_length_mm}mm, W={model_params.truss_width_mm}mm. "
        f"Cross-section: {model_params.cross_section}. "
        f"Loads: Q={model_params.load_q_kPa}kPa, Wind={model_params.wind_pressure_kPa}kPa. "
        f"Result: {json.dumps(result_summary, indent=2)}"
    )


# Flat input schema for the agent tool (easier for LLM to use)
class SensitivityAnalysisFlatInput(BaseModel):
    """Flat input parameters for sensitivity analysis - easier for agent to use"""

    truss_length: float = Field(default=10000, description="Truss length in mm")
    truss_width: float = Field(default=1000, description="Truss width in mm")
    n_divisions: int = Field(default=6, description="Number of divisions")
    cross_section: Literal["SHS50x4", "SHS75x4", "SHS100x4", "SHS150x4"] = Field(
        default="SHS100x4", description="Cross-section size for truss members"
    )
    load_q: float = Field(default=5, description="Gravitational load Q in kPa")
    wind_pressure: float = Field(default=1, description="Wind pressure in kPa")
    min_height: float = Field(
        default=500, description="Minimum truss height in mm for sensitivity analysis"
    )
    max_height: float = Field(
        default=3000, description="Maximum truss height in mm for sensitivity analysis"
    )
    n_steps: int = Field(
        default=10, description="Number of steps for sensitivity analysis"
    )


def calculate_sensitivity_analysis_tool() -> Any:
    from agents import FunctionTool

    return FunctionTool(
        name="calculate_sensitivity_analysis",
        description=(
            "Run sensitivity analysis on a rectangular truss beam varying the truss height using OpenSees in a Viktor app. "
            "Analyzes how truss depth (height) affects the maximum vertical deformation under gravitational and wind loads. "
            "Takes geometry parameters (truss length, width, divisions, cross-section), load parameters (gravitational load Q, wind pressure), "
            "and sensitivity parameters (min_height, max_height, n_steps). "
            "Returns deformation data for each height value, identifying optimal truss height for minimum deflection. "
            "URL: https://beta.viktor.ai/workspaces/4702/app/editor/2437"
        ),
        params_json_schema=SensitivityAnalysisFlatInput.model_json_schema(),
        on_invoke_tool=calculate_sensitivity_analysis_func,
    )


if __name__ == "__main__":
    sensitivity_input = SensitivityAnalysisInput(
        step_1=SensitivityAnalysisStep1(
            truss_length=10000,
            truss_width=1000,
            n_divisions=6,
            cross_section="SHS100x4",
        ),
        step_2=SensitivityAnalysisStep2(
            load_q=5,
            wind_pressure=1,
        ),
        step_4=SensitivityAnalysisStep4(
            min_height=500,
            max_height=3000,
            n_steps=10,
        ),
    )
    tool = SensitivityAnalysisTool(sensitivity_input=sensitivity_input)

    result = tool.run_and_parse()

    import pprint

    pprint.pp(result.model_dump())
    print(f"\nAnalyzed {len(result.sensitivity_analysis)} data points")
