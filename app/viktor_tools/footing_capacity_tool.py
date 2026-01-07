from typing import Literal, Any
from pydantic import BaseModel, Field
import requests
import logging
import json
from .base import ViktorTool

logger = logging.getLogger(__name__)


class FootingCapacityInput(BaseModel):
    # Geometry (mm for Viktor app)
    footing_B_mm: float = Field(
        default=2000, description="Footing width B in millimeters", ge=200, le=20000
    )
    footing_L_mm: float = Field(
        default=2500, description="Footing length L in millimeters", ge=200, le=20000
    )
    footing_Df_mm: float = Field(
        default=1000,
        description="Embedment depth to base Df in millimeters",
        ge=0,
        le=10000,
    )
    footing_t_mm: float = Field(
        default=500, description="Footing thickness in millimeters", ge=100, le=3000
    )

    # Soil properties
    gamma_kN_m3: float = Field(
        default=18.0, description="Soil unit weight in kN/m³", ge=0.0, le=30.0
    )
    c_kPa: float = Field(
        default=0.0, description="Soil cohesion in kPa", ge=0.0, le=300.0
    )
    phi_deg: float = Field(
        default=30.0, description="Soil friction angle in degrees", ge=0.0, le=45.0
    )
    mu_base: float = Field(
        default=0.50, description="Base friction coefficient", ge=0.0, le=1.2
    )

    # Sliding options
    sliding_direction: Literal["Along L", "Along B"] = Field(
        default="Along L", description="Direction of sliding resistance"
    )
    include_adhesion: bool = Field(
        default=False, description="Include base adhesion (α·c) in sliding resistance"
    )
    alpha_adhesion: float = Field(
        default=0.5, description="Adhesion factor", ge=0.0, le=1.0
    )
    include_passive: bool = Field(
        default=True,
        description="Include passive earth pressure resistance from embedment",
    )
    passive_reduction: float = Field(
        default=0.5, description="Passive resistance reduction factor", ge=0.0, le=1.0
    )

    # Loads
    V_kN: float = Field(
        default=1000.0, description="Applied vertical load in kN", ge=0.0, le=100000.0
    )
    H_kN: float = Field(
        default=150.0, description="Applied horizontal load in kN", ge=0.0, le=100000.0
    )

    # Safety factors
    FS_bearing: float = Field(
        default=3.0,
        description="Required safety factor for bearing capacity",
        ge=1.0,
        le=10.0,
    )
    FS_sliding: float = Field(
        default=1.5,
        description="Required safety factor for sliding resistance",
        ge=1.0,
        le=10.0,
    )


class FootingGeometry(BaseModel):
    B_mm: float = Field(description="Footing width in millimeters")
    L_mm: float = Field(description="Footing length in millimeters")
    Df_mm: float = Field(description="Embedment depth to base in millimeters")
    t_mm: float = Field(description="Footing thickness in millimeters")
    Area_m2: float = Field(description="Footing plan area in square meters")


class SoilProperties(BaseModel):
    gamma_kN_m3: float = Field(description="Soil unit weight in kN/m³")
    c_kPa: float = Field(description="Soil cohesion in kPa")
    phi_deg: float = Field(description="Soil friction angle in degrees")
    mu_base: float = Field(description="Base friction coefficient")


class SlidingOptions(BaseModel):
    sliding_direction: str = Field(description="Direction of sliding resistance")
    include_adhesion: bool = Field(description="Whether base adhesion is included")
    alpha_adhesion: float = Field(description="Adhesion factor")
    include_passive: bool = Field(description="Whether passive resistance is included")
    passive_reduction: float = Field(description="Passive resistance reduction factor")


class LoadsInput(BaseModel):
    V_kN: float = Field(description="Applied vertical load in kN")
    H_kN: float = Field(description="Applied horizontal load in kN")


class SafetyFactors(BaseModel):
    FS_bearing: float = Field(description="Required safety factor for bearing capacity")
    FS_sliding: float = Field(
        description="Required safety factor for sliding resistance"
    )


class BearingCapacityFactors(BaseModel):
    Nc: float = Field(description="Bearing capacity factor for cohesion")
    Nq: float = Field(description="Bearing capacity factor for surcharge")
    Ngamma: float = Field(description="Bearing capacity factor for soil weight")
    shape_factors_sc_sq_sg: list[float] = Field(
        description="Shape factors [sc, sq, sg]"
    )
    depth_factors_dc_dq_dg: list[float] = Field(
        description="Depth factors [dc, dq, dg]"
    )


class BearingCapacityResults(BaseModel):
    q_surcharge_kPa: float = Field(
        description="Surcharge pressure at foundation level in kPa"
    )
    c_term_kPa: float = Field(
        description="Cohesion term contribution to bearing capacity in kPa"
    )
    q_term_kPa: float = Field(
        description="Surcharge term contribution to bearing capacity in kPa"
    )
    gamma_term_kPa: float = Field(
        description="Soil weight term contribution to bearing capacity in kPa"
    )
    qult_gross_kPa: float = Field(description="Ultimate gross bearing capacity in kPa")
    qult_net_kPa: float = Field(description="Ultimate net bearing capacity in kPa")
    qallow_gross_kPa: float = Field(
        description="Allowable gross bearing capacity in kPa"
    )
    qallow_net_kPa: float = Field(description="Allowable net bearing capacity in kPa")
    Vallow_kN: float = Field(description="Allowable vertical load in kN")
    q_applied_kPa: float = Field(description="Applied bearing pressure in kPa")
    FS_bearing_actual: float | str = Field(
        description="Actual factor of safety for bearing (may be 'infinity')"
    )


class SlidingResistanceResults(BaseModel):
    Kp_passive: float = Field(description="Rankine passive earth pressure coefficient")
    R_friction_kN: float = Field(description="Friction resistance in kN")
    R_adhesion_kN: float = Field(description="Adhesion resistance in kN")
    R_passive_kN: float = Field(description="Passive earth pressure resistance in kN")
    Rult_kN: float = Field(description="Ultimate sliding resistance in kN")
    Hallow_kN: float = Field(description="Allowable horizontal load in kN")
    FS_sliding_actual: float | str = Field(
        description="Actual factor of safety for sliding (may be 'infinity')"
    )


class FootingCapacityOutput(BaseModel):
    inputs: dict
    results: dict


class FootingCapacityTool(ViktorTool):
    def __init__(
        self,
        footing_input: FootingCapacityInput,
        workspace_id: int = 4682,
        entity_id: int = 2404,
        method_name: str = "download_results_json",
    ):
        super().__init__(workspace_id, entity_id)
        self.footing_input = footing_input
        self.method_name = method_name

    def build_payload(self) -> dict[str, Any]:
        return {
            "method_name": self.method_name,
            "params": self.footing_input.model_dump(),
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

    def run_and_parse(self) -> FootingCapacityOutput:
        content = self.run_and_download()
        return FootingCapacityOutput(**content)


async def calculate_footing_capacity_func(ctx: Any, args: str) -> str:
    payload = FootingCapacityInput.model_validate_json(args)

    tool = FootingCapacityTool(footing_input=payload)
    result = tool.run_and_parse()

    # Extract key results for summary
    bearing = result.results.get("bearing_capacity", {})
    sliding = result.results.get("sliding_resistance", {})
    geom = result.inputs.get("geometry", {})

    qult_gross = bearing.get("qult_gross_kPa", 0)
    qallow_gross = bearing.get("qallow_gross_kPa", 0)
    Vallow = bearing.get("Vallow_kN", 0)
    FS_bearing = bearing.get("FS_bearing_actual", "N/A")

    Rult = sliding.get("Rult_kN", 0)
    Hallow = sliding.get("Hallow_kN", 0)
    FS_sliding = sliding.get("FS_sliding_actual", "N/A")

    result_summary = {
        "footing_dimensions": f"B={geom.get('B_mm')}mm, L={geom.get('L_mm')}mm, Df={geom.get('Df_mm')}mm",
        "footing_area_m2": geom.get("Area_m2"),
        "bearing": {
            "ultimate_capacity_kPa": qult_gross,
            "allowable_capacity_kPa": qallow_gross,
            "allowable_load_kN": Vallow,
            "actual_FS": FS_bearing,
        },
        "sliding": {
            "ultimate_resistance_kN": Rult,
            "allowable_load_kN": Hallow,
            "actual_FS": FS_sliding,
        },
    }

    return (
        f"Footing capacity analysis completed successfully. "
        f"Footing: B={geom.get('B_mm')}mm, L={geom.get('L_mm')}mm, Area={geom.get('Area_m2')}m². "
        f"Bearing: Ultimate={qult_gross}kPa, Allowable={qallow_gross}kPa, Vallow={Vallow}kN, FS={FS_bearing}. "
        f"Sliding: Ultimate={Rult}kN, Hallow={Hallow}kN, FS={FS_sliding}. "
        f"Result: {json.dumps(result_summary, indent=2)}"
    )


def calculate_footing_capacity_tool() -> Any:
    from agents import FunctionTool

    return FunctionTool(
        name="calculate_footing_capacity",
        description=(
            "Calculate bearing capacity and sliding resistance for shallow foundation footings using Terzaghi-Meyerhof theory. "
            "Computes ultimate and allowable bearing capacities, sliding resistance including friction, adhesion, and passive pressure. "
            "Takes footing geometry, soil properties (unit weight, cohesion, friction angle), loading conditions, and safety factors. "
            "Returns detailed analysis including bearing capacity factors, allowable loads, and actual factors of safety."
        ),
        params_json_schema=FootingCapacityInput.model_json_schema(),
        on_invoke_tool=calculate_footing_capacity_func,
    )


if __name__ == "__main__":
    footing_input = FootingCapacityInput(
        footing_B_mm=2000,
        footing_L_mm=2500,
        footing_Df_mm=1000,
        footing_t_mm=500,
        gamma_kN_m3=18.0,
        c_kPa=0.0,
        phi_deg=30.0,
        mu_base=0.50,
        V_kN=1000.0,
        H_kN=150.0,
    )
    tool = FootingCapacityTool(footing_input=footing_input)

    result = tool.run_and_parse()

    import pprint

    print("\n=== BEARING CAPACITY RESULTS ===")
    pprint.pp(result.results.get("bearing_capacity", {}))
    print("\n=== SLIDING RESISTANCE RESULTS ===")
    pprint.pp(result.results.get("sliding_resistance", {}))
