import sys
from app.viktor_tools.footing_capacity_tool import (
    FootingCapacityInput,
    FootingCapacityTool,
    FootingCapacityOutput,
)
from app.viktor_tools.seismic_load_tool import (
    SeismicLoadInput,
    SeismicLoadTool,
    SeismicLoadOutput,
)
from app.viktor_tools.wind_loads_tool import (
    WindLoadInput,
    WindLoadTool,
    WindLoadOutput,
)
from app.viktor_tools.structural_analysis_tool import (
    StructuralAnalysisInput,
    StructuralAnalysisStep1,
    StructuralAnalysisStep2,
    StructuralAnalysisTool,
    StructuralAnalysisOutput,
)
from app.viktor_tools.sensitivity_analysis_tool import (
    SensitivityAnalysisInput,
    SensitivityAnalysisStep1,
    SensitivityAnalysisStep2,
    SensitivityAnalysisStep4,
    SensitivityAnalysisTool,
    SensitivityAnalysisOutput,
)
from app.viktor_tools.geometry_tool import (
    GeometryGeneration,
    GeometryGenerationTool,
    Model,
)


def test_footing_capacity():
    """Test FootingCapacityTool.run_and_parse returns FootingCapacityOutput"""
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

    # Verify type
    assert isinstance(result, FootingCapacityOutput), (
        f"Expected FootingCapacityOutput, got {type(result)}"
    )

    assert "bearing_capacity" in result.results
    assert "sliding_resistance" in result.results


def test_seismic_load():
    """Test SeismicLoadTool.run_and_parse returns SeismicLoadOutput"""
    seismic_input = SeismicLoadInput(
        soil_category="D",
        region="B",
        importance_level="2",
        tl_s=6.0,
        max_period_s=4.0,
    )
    tool = SeismicLoadTool(seismic_input=seismic_input)

    result = tool.run_and_parse()

    # Verify type
    assert isinstance(result, SeismicLoadOutput), (
        f"Expected SeismicLoadOutput, got {type(result)}"
    )

    assert result.seismic_parameters is not None
    assert len(result.spectrum_data.periods_s) > 0


def test_wind_loads():
    """Test WindLoadTool.run_and_parse returns WindLoadOutput"""
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

    # Verify type
    assert isinstance(result, WindLoadOutput), (
        f"Expected WindLoadOutput, got {type(result)}"
    )

    assert result.qh_kpa > 0
    assert result.q_kpa > 0


def test_structural_analysis():
    """Test StructuralAnalysisTool.run_and_parse returns StructuralAnalysisOutput"""
    structural_input = StructuralAnalysisInput(
        step_1=StructuralAnalysisStep1(
            truss_length=10000,
            truss_width=1000,
            truss_height=1500,
            n_divisions=6,
            cross_section="SHS100x4",
        ),
        step_2=StructuralAnalysisStep2(
            load_q=5,
            wind_pressure=1,
        ),
    )
    tool = StructuralAnalysisTool(structural_input=structural_input)

    result = tool.run_and_parse()

    # Verify type
    assert isinstance(result, StructuralAnalysisOutput), (
        f"Expected StructuralAnalysisOutput, got {type(result)}"
    )

    assert result.critical_combination is not None
    assert result.max_displacements_mm is not None


def test_sensitivity_analysis():
    """Test SensitivityAnalysisTool.run_and_parse returns SensitivityAnalysisOutput"""
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

    # Verify type
    assert isinstance(result, SensitivityAnalysisOutput), (
        f"Expected SensitivityAnalysisOutput, got {type(result)}"
    )

    assert len(result.sensitivity_analysis) > 0


def test_geometry_generation():
    """Test GeometryGenerationTool.run_and_parse returns Model"""
    geometry = GeometryGeneration(
        truss_length=10000,
        truss_width=1000,
        truss_height=1500,
        n_divisions=6,
        cross_section="SHS100x4",
    )
    tool = GeometryGenerationTool(geometry=geometry)

    result = tool.run_and_parse()

    # Verify type
    assert isinstance(result, Model), f"Expected Model, got {type(result)}"

    assert result.metadata.total_nodes > 0
    assert result.metadata.total_lines > 0


def run_all_tests():
    """Run all tool tests and report results (standalone mode)"""
    print("\n" + "#" * 60)
    print("VIKTOR TOOLS - run_and_parse VALIDATION TESTS")
    print("#" * 60)

    tests = [
        ("FootingCapacityTool", test_footing_capacity),
        ("SeismicLoadTool", test_seismic_load),
        ("WindLoadTool", test_wind_loads),
        ("StructuralAnalysisTool", test_structural_analysis),
        ("SensitivityAnalysisTool", test_sensitivity_analysis),
        ("GeometryGenerationTool", test_geometry_generation),
    ]

    results = {}
    for name, test_func in tests:
        try:
            test_func()
            results[name] = "✅ PASSED"
        except AssertionError as e:
            results[name] = f"❌ FAILED: {e}"
        except Exception as e:
            results[name] = f"❌ ERROR: {type(e).__name__}: {e}"

    # Summary
    print("TEST SUMMARY")
    print("#" * 60)
    for name, status in results.items():
        print(f"  {name}: {status}")

    passed = sum(1 for s in results.values() if s.startswith("✅"))
    total = len(results)
    print(f"Total: {passed}/{total} tests passed")

    if passed == total:
        print("All tests passed!✅")
    else:
        print("Some tests failed!❌")
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
