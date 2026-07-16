from datetime import datetime
from datetime import date
from pydantic import BaseModel, ConfigDict, Field

from app.modules.deliveries.models import DeliveryStatus
from app.modules.orders.models import OrderStatus


class ChefCustomerResponse(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    address: str | None = None


class ChefOrderDeliveryResponse(BaseModel):
    id: int
    driver_id: int | None = None
    status: DeliveryStatus
    delivery_address: str
    scheduled_at: datetime | None = None
    picked_up_at: datetime | None = None
    delivered_at: datetime | None = None


class ChefOrderResponse(BaseModel):
    id: int
    order_number: str
    status: OrderStatus

    user_id: int
    subscription_id: int | None = None
    plan_id: int | None = None

    total_amount: float

    delivery_date: datetime | None = None
    delivery_address: str | None = None
    delivery_notes: str | None = None

    items: list[dict] | None = None

    created_at: datetime
    updated_at: datetime

    customer: ChefCustomerResponse | None = None
    delivery: ChefOrderDeliveryResponse | None = None


class ChefDashboardResponse(BaseModel):
    total_orders: int
    pending_orders: int
    confirmed_orders: int
    preparing_orders: int
    ready_for_delivery_orders: int
    out_for_delivery_orders: int
    delivered_orders: int
    cancelled_orders: int

    deliveries_needed: int
    assigned_deliveries: int
    available_drivers: int
    total_active_drivers: int


class AssignChefDriverRequest(BaseModel):
    driver_id: int = Field(..., ge=1)
    scheduled_at: datetime | None = None


class ChefDriverResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    full_name: str
    email: str
    phone: str
    location: str | None = None
    is_active: bool

    active_deliveries: int
    available: bool


class ChefStatusResponse(BaseModel):
    message: str
    order: ChefOrderResponse
    
class ChefMealSummaryItem(BaseModel):
    meal_id: int | None = None
    meal_name: str
    quantity: int


class ChefMealSummaryResponse(BaseModel):
    date: date
    total_orders: int
    total_meals: int
    meals: list[ChefMealSummaryItem]


class ChefAllergySummaryItem(BaseModel):
    allergy: str
    customer_count: int
    order_count: int


class ChefAllergyCustomerResponse(BaseModel):
    user_id: int
    full_name: str
    phone: str | None = None
    allergies: list[str]
    order_ids: list[int]


class ChefAllergySummaryResponse(BaseModel):
    date: date
    total_orders: int
    customers_with_allergies: int
    allergies: list[ChefAllergySummaryItem]
    customers: list[ChefAllergyCustomerResponse]    


class ChefDeliveryAssignmentResponse(BaseModel):
    message: str
    delivery_id: int
    order_id: int
    driver_id: int
    delivery_status: DeliveryStatus
    order_status: OrderStatus

    model_config = ConfigDict(from_attributes=True)