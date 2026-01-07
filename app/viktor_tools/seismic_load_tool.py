from typing import Literal, Any
from pydantic import BaseModel, Field
import requests
import logging
import json
from .base import ViktorTool

logger = logging.getLogger(__name__)


class SeismicLoadInput(BaseModel):
    soil_category: Literal["A", "B", "C", "D", "F"] = Field(
        default="D", description="Soil category"
    )
    region: Literal["A", "B", "C", "D"] = Field(
        default="B", description="Seismic region"
    )
    importance_level: Literal["1", "2", "3"] = Field(
        default="2", description="Importance level"
    )
    tl_s: float = Field(default=6.0, description="Long-period transition TL in seconds")
    max_period_s: float = Field(default=4.0, description="Maximum period in seconds")
    n_points: int = Field(
        default=401, description="Number of points for spectrum calculation"
    )
    scale_by_importance: bool = Field(
        default=True, description="Scale by importance factor"
    )


class SeismicParameters(BaseModel):
    Ss_g: float = Field(
        description="Mapped MCE (Maximum Considered Earthquake) short-period spectral acceleration in g"
    )
    S1_g: float = Field(
        description="Mapped MCE 1-second period spectral acceleration in g"
    )
    Fa: float = Field(description="Short-period site coefficient")
    Fv: float = Field(description="Long-period site coefficient")
    SMS_g: float = Field(
        description="Site-modified short-period spectral acceleration in g"
    )
    SM1_g: float = Field(
        description="Site-modified 1-second period spectral acceleration in g"
    )
    SDS_g: float = Field(
        description="Design short-period spectral acceleration (2/3 of SMS) in g"
    )
    SD1_g: float = Field(
        description="Design 1-second period spectral acceleration (2/3 of SM1) in g"
    )
    T0_s: float = Field(
        description="Short period transition (0.2 * SD1/SDS) in seconds"
    )
    Ts_s: float = Field(description="Long period transition (SD1/SDS) in seconds")
    TL_s: float = Field(description="Long-period transition period in seconds")
    Ie: float = Field(description="Importance factor based on risk category")


class SpectrumData(BaseModel):
    periods_s: list[float]
    spectral_acceleration_g: list[float]


class SeismicLoadOutput(BaseModel):
    inputs: dict
    seismic_parameters: SeismicParameters
    spectrum_data: SpectrumData


class SeismicLoadTool(ViktorTool):
    def __init__(
        self,
        seismic_input: SeismicLoadInput,
        workspace_id: int = 4680,
        entity_id: int = 2403,
        method_name: str = "download_summary_json",
    ):
        super().__init__(workspace_id, entity_id)
        self.seismic_input = seismic_input
        self.method_name = method_name

    def build_payload(self) -> dict[str, Any]:
        return {
            "method_name": self.method_name,
            "params": self.seismic_input.model_dump(),
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

    def run_and_parse(self) -> SeismicLoadOutput:
        content = self.run_and_download()
        return SeismicLoadOutput(**content)


async def calculate_seismic_loads_func(ctx: Any, args: str) -> str:
    payload = SeismicLoadInput.model_validate_json(args)

    tool = SeismicLoadTool(seismic_input=payload)
    result = tool.run_and_parse()

    params = result.seismic_parameters
    num_points = len(result.spectrum_data.periods_s)
    max_sa = (
        max(result.spectrum_data.spectral_acceleration_g)
        if result.spectrum_data.spectral_acceleration_g
        else 0
    )

    result_summary = {
        "soil_category": payload.soil_category,
        "region": payload.region,
        "importance_level": payload.importance_level,
        "importance_factor_Ie": params.Ie,
        "design_spectral_acceleration_SDS_g": params.SDS_g,
        "design_spectral_acceleration_SD1_g": params.SD1_g,
        "period_T0_s": params.T0_s,
        "period_Ts_s": params.Ts_s,
        "period_TL_s": params.TL_s,
        "spectrum_points": num_points,
        "max_spectral_acceleration_g": round(max_sa, 3),
    }

    return (
        f"Seismic load analysis completed successfully. "
        f"Soil Category: {payload.soil_category}, Region: {payload.region}, Importance Level: {payload.importance_level}. "
        f"Design spectral accelerations: SDS={params.SDS_g}g, SD1={params.SD1_g}g. "
        f"Key periods: T0={params.T0_s}s, Ts={params.Ts_s}s, TL={params.TL_s}s. "
        f"Importance factor Ie={params.Ie}. "
        f"Generated {num_points}-point response spectrum. "
        f"Result: {json.dumps(result_summary, indent=2)}"
    )


def calculate_seismic_loads_tool() -> Any:
    from agents import FunctionTool

    return FunctionTool(
        name="calculate_seismic_loads",
        description=(
            "Calculate seismic loads and design response spectrum for a building structure in a Viktor app based on ASCE 7 standards. "
            "Computes design spectral accelerations (SDS, SD1), site coefficients (Fa, Fv), and generates a complete response spectrum. "
            "Takes soil category, seismic region, importance level, and period parameters. "
            "Returns seismic analysis results including spectral accelerations in g and characteristic periods."
        ),
        params_json_schema=SeismicLoadInput.model_json_schema(),
        on_invoke_tool=calculate_seismic_loads_func,
    )


if __name__ == "__main__":
    seismic_input = SeismicLoadInput(
        soil_category="D",
        region="B",
        importance_level="2",
        tl_s=6.0,
        max_period_s=4.0,
    )
    tool = SeismicLoadTool(seismic_input=seismic_input)

    result = tool.run_and_parse()

    import pprint

    pprint.pp(result.seismic_parameters)
    print(f"\nSpectrum has {len(result.spectrum_data.periods_s)} points")
