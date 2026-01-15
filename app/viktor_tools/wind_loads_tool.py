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
    bridge_length: float = Field(default=20000, description="Bridge length in mm")
    bridge_width: float = Field(default=4500, description="Bridge width in mm")
    bridge_height: float = Field(default=3000, description="Bridge height in mm")
    roof_pitch_angle: float = Field(
        default=12, description="Roof pitch angle in degrees"
    )
    n_divisions: int = Field(default=4, description="Number of divisions")
    cross_section: Literal[
        "HSS200×200×8", "HSS250×250×10", "HSS300×300×12", "HSS350×350×16"
    ] = Field(default="HSS200×200×8", description="Cross-section size")
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
    force_coefficient_cf: float = Field(default=1.6, description="Force coefficient Cf")


class WindLoadOutput(BaseModel):
    risk_category: str
    site_elevation_m: float
    bridge_length_mm: float
    bridge_width_mm: float
    bridge_height_mm: float
    n_divisions: int
    cross_section: str
    exposure_category: str
    wind_speed_ms: float
    kzt: float
    kd: float
    g: float
    Af_members_m2: float
    Af_total_m2: float
    Ag_m2: float
    solidity_ratio_epsilon: float
    velocity_pressure_coeff: float
    kz: float
    qz_kpa: float
    p_kpa: float
    cf: float


class WindLoadTool(ViktorTool):
    def __init__(
        self,
        wind_input: WindLoadInput,
        workspace_id: int = 4713,
        entity_id: int = 2452,
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
        "velocity_pressure_qz_kpa": result.qz_kpa,
        "design_pressure_p_kpa": result.p_kpa,
        "kz": result.kz,
        "Af_total_m2": result.Af_total_m2,
        "Ag_m2": result.Ag_m2,
        "solidity_ratio_epsilon": result.solidity_ratio_epsilon,
        "cf": result.cf,
    }

    return (
        f"Wind load analysis completed successfully. "
        f"Risk Category: {result.risk_category}, Exposure: {result.exposure_category}. "
        f"Wind speed: {result.wind_speed_ms} m/s. "
        f"Velocity pressure (qz): {result.qz_kpa} kPa. "
        f"Design pressure (p): {result.p_kpa} kPa. "
        f"Kz coefficient: {result.kz}. "
        f"Result: {json.dumps(result_summary, indent=2)}"
    )


def calculate_wind_loads_tool() -> Any:
    from agents import FunctionTool

    return FunctionTool(
        name="calculate_wind_loads",
        description=(
            "Calculate wind loads for a bridge structure in a Viktor app based on ASCE 7 standards. "
            "Computes velocity pressure (qz), design pressure (p), and projected area parameters. "
            "Takes bridge dimensions, wind speed, exposure category, and various factors. "
            "Returns wind load analysis results including pressures in kPa, projected areas, and solidity ratio."
        ),
        params_json_schema=WindLoadInput.model_json_schema(),
        on_invoke_tool=calculate_wind_loads_func,
    )


if __name__ == "__main__":
    wind_input = WindLoadInput(
        risk_category="II",
        site_elevation_m=138.0,
        bridge_length=20000,
        bridge_width=4500,
        bridge_height=3000,
        roof_pitch_angle=12,
        n_divisions=4,
        cross_section="HSS200×200×8",
        exposure_category="C",
        wind_speed_ms=47.0,
    )
    tool = WindLoadTool(wind_input=wind_input)

    result = tool.run_and_parse()

    import pprint

    pprint.pp(result)
