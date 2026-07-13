from fastapi import APIRouter, HTTPException, Query

from app.modules.locations.data import SAUDI_LOCATIONS
from app.modules.locations.schemas import (
    CityResponse,
    LocationValidationResponse,
    RegionResponse,
    RegionSummaryResponse,
)


router = APIRouter(
    prefix="/locations",
    tags=["Locations"],
)


def normalize_value(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def find_region(region_code: str):
    normalized_code = normalize_value(region_code)

    for region in SAUDI_LOCATIONS:
        if normalize_value(region["code"]) == normalized_code:
            return region

    return None


def find_city(region: dict, city_code: str):
    normalized_code = normalize_value(city_code)

    for city in region["cities"]:
        if normalize_value(city["code"]) == normalized_code:
            return city

    return None


@router.get(
    "/",
    response_model=list[RegionResponse],
    summary="List Saudi regions and their cities",
)
def list_locations(
    search: str | None = Query(
        default=None,
        description="Search by English name, Arabic name, region code, or city code",
    ),
):
    if not search:
        return SAUDI_LOCATIONS

    search_value = search.strip().lower()
    results = []

    for region in SAUDI_LOCATIONS:
        matching_cities = [
            city
            for city in region["cities"]
            if (
                search_value in city["code"].lower()
                or search_value in city["name_en"].lower()
                or search_value in city["name_ar"]
            )
        ]

        region_matches = (
            search_value in region["code"].lower()
            or search_value in region["name_en"].lower()
            or search_value in region["name_ar"]
        )

        if region_matches:
            results.append(region)
        elif matching_cities:
            results.append(
                {
                    "code": region["code"],
                    "name_en": region["name_en"],
                    "name_ar": region["name_ar"],
                    "cities": matching_cities,
                }
            )

    return results


@router.get(
    "/regions",
    response_model=list[RegionSummaryResponse],
    summary="List Saudi regions",
)
def list_regions():
    return [
        {
            "code": region["code"],
            "name_en": region["name_en"],
            "name_ar": region["name_ar"],
        }
        for region in SAUDI_LOCATIONS
    ]


@router.get(
    "/regions/{region_code}",
    response_model=RegionResponse,
    summary="Get one region with its cities",
)
def get_region(region_code: str):
    region = find_region(region_code)

    if not region:
        raise HTTPException(
            status_code=404,
            detail="Region not found",
        )

    return region


@router.get(
    "/regions/{region_code}/cities",
    response_model=list[CityResponse],
    summary="List cities for one region",
)
def list_region_cities(region_code: str):
    region = find_region(region_code)

    if not region:
        raise HTTPException(
            status_code=404,
            detail="Region not found",
        )

    return region["cities"]


@router.get(
    "/validate",
    response_model=LocationValidationResponse,
    summary="Validate a region and city combination",
)
def validate_location(
    region_code: str = Query(...),
    city_code: str = Query(...),
):
    region = find_region(region_code)

    if not region:
        return LocationValidationResponse(valid=False)

    city = find_city(region, city_code)

    if not city:
        return LocationValidationResponse(
            valid=False,
            region={
                "code": region["code"],
                "name_en": region["name_en"],
                "name_ar": region["name_ar"],
            },
        )

    return LocationValidationResponse(
        valid=True,
        region={
            "code": region["code"],
            "name_en": region["name_en"],
            "name_ar": region["name_ar"],
        },
        city=city,
    )