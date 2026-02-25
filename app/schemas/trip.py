"""Schemas for boat trip status (departure, arrival, partial arrival)."""
from datetime import datetime
from typing import Optional, Literal, List
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
    image_url: Optional[str] = None


class BoatTripStatusResponse(BaseModel):
    """Boat status with respect to trip lifecycle."""

    boat_id: str
    boat_number: str
    trip_status: TripStatusType
    departure_details: Optional[DepartureDetails] = None
    has_open_departure: bool = False
    last_movement_at: Optional[datetime] = None
    last_movement_image_url: Optional[str] = None


class BoatMovementCreate(BaseModel):
    """Request to log a boat movement (departure, arrival, or partial arrival).
    Crew and port details are added in a separate step before final departure.
    image_url stores the crew-scan (or other) image URL for this movement type."""

    movement_type: Literal["departure", "arrival", "partial_arrival"]
    movement_at: Optional[datetime] = None  # Defaults to now if omitted
    partial_arrival_reason: Optional[PartialArrivalReason] = None
    partial_arrival_details: Optional[str] = None
    image_url: Optional[str] = None  # URL to image for this movement (e.g. crew scan)

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
    image_url: Optional[str] = None


class BoatMovementCrewMemberItem(BaseModel):
    """One crew member assigned to a specific trip (boat movement)."""

    crew_member_id: str


class BoatMovementCrewCreate(BaseModel):
    """Request body to attach crew list to a departure movement. Frontend sends only crew_members."""

    crew_members: List[BoatMovementCrewMemberItem]


class BoatMovementCrewResponse(BaseModel):
    """Summary of crew attached to a departure movement."""

    movement_id: str
    boat_id: str
    total_crew_count: int
    identified_crew_ids: List[str]
    unidentified_count: int
    success: bool = True
    message: str = "Crew members added successfully."


class BoatMovementInventoryCreate(BaseModel):
    """Request body to attach inventory details (diesel, ice, nets, plastics) to a movement."""

    diesel_liters: Optional[float] = None
    ice_blocks: Optional[int] = None
    fishing_net_count: Optional[int] = None
    plastic_bottle_count: Optional[int] = None
    plastic_bag_count: Optional[int] = None


class BoatMovementInventoryResponse(BaseModel):
    """Response for inventory attached to a movement."""

    movement_id: str
    boat_id: str
    diesel_liters: Optional[float] = None
    ice_blocks: Optional[int] = None
    fishing_net_count: Optional[int] = None
    plastic_bottle_count: Optional[int] = None
    plastic_bag_count: Optional[int] = None
    success: bool = True
    message: str = "Inventory added successfully."
