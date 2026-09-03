from movon_hr.modules.api import haversine_meters


def test_haversine_returns_zero_at_same_point() -> None:
    assert haversine_meters(-6.2, 106.8166, -6.2, 106.8166) == 0


def test_haversine_finds_nearby_point() -> None:
    assert 100 < haversine_meters(-6.2, 106.8166, -6.201, 106.8166) < 120
