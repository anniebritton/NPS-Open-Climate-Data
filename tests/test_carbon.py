from nps_climate_data import carbon as C


def test_estimate_returns_positive_numbers():
    b = C.estimate()
    d = b.to_dict()
    for k in ("ee_processing_g", "ee_egress_g", "local_analysis_g",
              "claude_api_g", "hosting_per_month_g", "per_view_g"):
        assert d[k] > 0, k
    assert d["total_build_g"] > 0


def test_estimate_scales_with_parks():
    small = C.estimate(n_parks=1)
    big = C.estimate(n_parks=63)
    assert big.ee_processing_g > small.ee_processing_g
    assert big.ee_egress_g > small.ee_egress_g


def test_claude_scales_with_tokens():
    a = C.estimate(claude_output_tokens=10_000)
    b = C.estimate(claude_output_tokens=200_000)
    assert b.claude_api_g > a.claude_api_g


def test_assumptions_exposed():
    b = C.estimate()
    d = b.to_dict()
    assert "assumptions" in d
    assert d["assumptions"]["grid_intensity_g_per_kWh"] > 0
