from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

class CustomerDriverAssignRequest(BaseModel):
    customer_id: int = Field(..., gt=0)
    driver_id: int = Field(..., gt=0)

    assignment_reason: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    notes: Optional[str] = None

class CustomerDriverUpdateRequest(BaseModel):
    driver_id: int = Field(..., gt=0)

    assignment_reason: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    notes: Optional[str] = None

class DriverSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str
    phone_number: Optional[str] = None

class CustomerSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str
    phone_number: Optional[str] = None

class AdminSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str

class CustomerDriverAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int

    customer: CustomerSummary

    driver: DriverSummary

    assigned_by_user: AdminSummary

    assignment_reason: Optional[str]

    notes: Optional[str]

    is_active: bool

    assigned_at: datetime

    ended_at: Optional[datetime]

    created_at: datetime

    updated_at: datetime

class CustomerDriverDetailsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    customer: CustomerSummary

    assignment: CustomerDriverAssignmentResponse

class DriverCustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assignment_id: int

    customer: CustomerSummary

    assigned_at: datetime

    assignment_reason: Optional[str]

class CustomerDriverAssignmentListResponse(BaseModel):
    total: int

    items: list[CustomerDriverAssignmentResponse]


class DriverCustomerListResponse(BaseModel):
    total: int

    items: list[DriverCustomerResponse]

class CustomerDriverDeleteResponse(BaseModel):
    success: bool

    message: str