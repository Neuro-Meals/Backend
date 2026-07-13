from pydantic import BaseModel


class CityResponse(BaseModel):
    code: str
    name_en: str
    name_ar: str


class RegionSummaryResponse(BaseModel):
    code: str
    name_en: str
    name_ar: str


class RegionResponse(RegionSummaryResponse):
    cities: list[CityResponse]


class LocationValidationResponse(BaseModel):
    valid: bool
    region: RegionSummaryResponse | None = None
    city: CityResponse | None = None