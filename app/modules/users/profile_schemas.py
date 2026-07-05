from pydantic import BaseModel, Field
from app.modules.users.models import FitnessGoal, Gender


class ProfileUpdate(BaseModel):
    first_name: str | None = Field(None, min_length=2, max_length=100)
    last_name: str | None = Field(None, min_length=2, max_length=100)
    phone: str | None = Field(None, min_length=8)

    location: str | None = None
    address: str | None = None

    gender: Gender | None = None
    age: int | None = None
    height_cm: float | None = None
    weight_kg: float | None = None

    fitness_goal: FitnessGoal | None = None
    dietary_preference: str | None = None
    allergies: list[str] | None = None