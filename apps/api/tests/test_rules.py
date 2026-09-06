from movon_hr.modules.api import (
    OFFICE_LATITUDE,
    OFFICE_LONGITUDE,
    OFFICE_RADIUS_METERS,
    allowed_check_in_radius_meters,
    haversine_meters,
    reset_demo_store,
)


def test_haversine_returns_zero_at_same_point() -> None:
    assert haversine_meters(OFFICE_LATITUDE, OFFICE_LONGITUDE, OFFICE_LATITUDE, OFFICE_LONGITUDE) == 0


def test_haversine_finds_nearby_point() -> None:
    assert 100 < haversine_meters(OFFICE_LATITUDE, OFFICE_LONGITUDE, -6.201, OFFICE_LONGITUDE) < 120


def test_accuracy_credit_is_capped_to_prevent_home_check_in() -> None:
    reset_demo_store()
    assert allowed_check_in_radius_meters(10) == OFFICE_RADIUS_METERS + 10
    assert allowed_check_in_radius_meters(500) == OFFICE_RADIUS_METERS + 50
