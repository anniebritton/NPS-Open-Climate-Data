from nps_climate_data import carbon as C


def test_estimate_returns_positive_numbers():
    b = C.estimate(n_commits=10)
    d = b.to_dict()
    for k in ("ee_processing_g", "ee_egress_g", "local_analysis_g",
              "claude_api_g", "ci_actions_g", "hosting_per_month_g", "per_view_g"):
        assert d[k] > 0, k
    assert d["total_build_g"] > 0


def test_estimate_scales_with_parks():
    small = C.estimate(n_parks=1)
    big = C.estimate(n_parks=63)
    assert big.ee_processing_g > small.ee_processing_g
    assert big.ee_egress_g > small.ee_egress_g


def test_claude_and_ci_scale_with_commits():
    few = C.estimate(n_commits=1)
    many = C.estimate(n_commits=50)
    assert many.claude_api_g > few.claude_api_g
    assert many.ci_actions_g > few.ci_actions_g


def test_assumptions_exposed():
    b = C.estimate()
    d = b.to_dict()
    assert "assumptions" in d
    assert d["assumptions"]["grid_intensity_g_per_kWh"] > 0
