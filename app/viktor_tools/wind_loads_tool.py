from typing import Literal, Any
from pydantic import BaseModel, Field
import logging
import json
from .base import ViktorTool

logger = logging.getLogger(__name__)


class WindLoadInput(BaseModel):
    risk_category: Literal["I", "II", "III", "IV"] = Field(
        default="II", description="Risk category"
    )
    site_elevation_m: float = Field(
        default=138.0, description="Site elevation in meters"
    )
    structure_length_mm: float = Field(
        default=9500, description="Building length in mm"
    )
    structure_width_mm: float = Field(default=9500, description="Building width in mm")
    mean_roof_height_mm: float = Field(
        default=3660, description="Mean roof height in mm"
    )
    roof_pitch_angle: float = Field(
        default=12, description="Roof pitch angle in degrees"
    )
    exposure_category: Literal["B", "C", "D"] = Field(
        default="C", description="Exposure category"
    )
    wind_speed_ms: float = Field(default=47.0, description="Basic wind speed in m/s")
    topographic_factor_kzt: float = Field(
        default=1.0, description="Topographic factor Kzt"
    )
    directionality_factor_kd: float = Field(
        default=0.85, description="Directionality factor Kd"
    )
    gust_effect_factor_g: float = Field(
        default=0.85, description="Gust effect factor G"
    )


class WindLoadOutput(BaseModel):
    risk_category: str
    site_elevation_m: float
    length_mm: float
    width_mm: float
    mean_roof_height_mm: float
    roof_pitch_angle_deg: float
    roof_rise_mm: float
    eave_height_mm: float
    ridge_height_mm: float
    exposure_category: str
    wind_speed_ms: float
    kz: float
    kzt: float
    kd: float
    g: float
    qh_kpa: float
    q_kpa: float


class WindLoadTool(ViktorTool):
    def __init__(
        self,
        wind_input: WindLoadInput,
        workspace_id: int = 4675,
        entity_id: int = 2397,
        method_name: str = "download_json_data",
    ):
        super().__init__(workspace_id, entity_id)
        self.wind_input = wind_input
        self.method_name = method_name

    def build_payload(self) -> dict[str, Any]:
        return {
            "method_name": self.method_name,
            "params": self.wind_input.model_dump(),
            "poll_result": True,
        }

    def run_and_download(self) -> dict:
        job = self.run()
        return self.download_result(job)

    def run_and_parse(self) -> WindLoadOutput:
        content = self.run_and_download()
        return WindLoadOutput(**content)


async def calculate_wind_loads_func(ctx: Any, args: str) -> str:
    payload = WindLoadInput.model_validate_json(args)

    tool = WindLoadTool(wind_input=payload)
    result = tool.run_and_parse()

    result_summary = {
        "risk_category": result.risk_category,
        "exposure_category": result.exposure_category,
        "wind_speed_ms": result.wind_speed_ms,
        "velocity_pressure_qh_kpa": result.qh_kpa,
        "design_pressure_q_kpa": result.q_kpa,
        "kz": result.kz,
        "roof_rise_mm": result.roof_rise_mm,
        "eave_height_mm": result.eave_height_mm,
        "ridge_height_mm": result.ridge_height_mm,
    }

    return (
        f"Wind load analysis completed successfully. "
        f"Risk Category: {result.risk_category}, Exposure: {result.exposure_category}. "
        f"Wind speed: {result.wind_speed_ms} m/s. "
        f"Velocity pressure (qh): {result.qh_kpa} kPa. "
        f"Design pressure (q): {result.q_kpa} kPa. "
        f"Kz coefficient: {result.kz}. "
        f"Result: {json.dumps(result_summary, indent=2)}"
    )


def calculate_wind_loads_tool() -> Any:
    from agents import FunctionTool

    return FunctionTool(
        name="calculate_wind_loads",
        description=(
            "Calculate wind loads for a building structure in a Viktor app based on ASCE 7 standards. "
            "Computes velocity pressure, design pressure, and roof geometry parameters. "
            "Takes building dimensions, wind speed, exposure category, and various factors. "
            "Returns wind load analysis results including pressures in kPa and derived roof heights."
        ),
        params_json_schema=WindLoadInput.model_json_schema(),
        on_invoke_tool=calculate_wind_loads_func,
    )


if __name__ == "__main__":
    wind_input = WindLoadInput(
        risk_category="II",
        site_elevation_m=138.0,
        structure_length_mm=9500,
        structure_width_mm=9500,
        mean_roof_height_mm=3660,
        roof_pitch_angle=12,
        exposure_category="C",
        wind_speed_ms=47.0,
    )
    tool = WindLoadTool(wind_input=wind_input)

    result = tool.run_and_parse()

    import pprint

    pprint.pp(result)
