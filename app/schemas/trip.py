"""Schemas for boat trip status (departure, arrival, partial arrival)."""
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, model_validator

TripStatusType = Literal["docked", "sailing", "arrived", "partial_arrival"]

PartialArrivalReason = Literal[
    "system_error",
    "left_from_other_port",
    "emergency",
    "data_migration",
    "other",
]


class DepartureDetails(BaseModel):
    """Shown when boat has an open departure (sailing)."""

    departure_at: datetime
    from_port: str
    vessel_type: Optional[str] = None
    crew_count: Optional[int] = None
    status_label: str = "Sailing"


class BoatTripStatusResponse(BaseModel):
    """Boat status with respect to trip lifecycle."""

    boat_id: str
    boat_number: str
    trip_status: TripStatusType
    departure_details: Optional[DepartureDetails] = None
    has_open_departure: bool = False
    last_movement_at: Optional[datetime] = None


class BoatMovementCreate(BaseModel):
    """Request to log a boat movement (departure, arrival, or partial arrival).
    Crew and port details are added in a separate step before final departure."""

    movement_type: Literal["departure", "arrival", "partial_arrival"]
    movement_at: Optional[datetime] = None  # Defaults to now if omitted
    partial_arrival_reason: Optional[PartialArrivalReason] = None
    partial_arrival_details: Optional[str] = None

    @model_validator(mode="after")
    def validate_partial_arrival(self):
        if self.movement_type == "partial_arrival":
            if not self.partial_arrival_reason:
                raise ValueError("partial_arrival_reason is required for partial_arrival")
            if self.partial_arrival_reason == "other" and not (
                self.partial_arrival_details and self.partial_arrival_details.strip()
            ):
                raise ValueError(
                    "partial_arrival_details is required when partial_arrival_reason is 'other'"
                )
        return self


class BoatMovementResponse(BaseModel):
    """Response after creating a boat movement."""

    id: str
    boat_id: str
    movement_type: Literal["departure", "arrival", "partial_arrival"]
    movement_at: datetime
    partial_arrival_reason: Optional[str] = None
    partial_arrival_details: Optional[str] = None
