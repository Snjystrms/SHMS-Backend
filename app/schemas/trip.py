"""Schemas for boat trip status (departure, arrival, partial arrival)."""
from datetime import datetime
from typing import Optional, Literal, List, Dict
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
    open_departure_movement_id: Optional[str] = None
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


# ----- Arrival check (crew + inventory) -----

class ArrivalCrewScanRequest(BaseModel):
    """Optional: pass image_url if image already uploaded; otherwise use multipart file."""

    image_url: Optional[str] = None


class ArrivalCrewMemberStatus(BaseModel):
    """One crew member with arrival status: present (matched at arrival) or missing."""

    crew_member_id: str
    name: str
    is_pilot: bool = False
    status: Literal["present", "missing"]  # present = identified in arrival scan; missing = in departure, not in scan


class ArrivalUnidentifiedEntry(BaseModel):
    """One unidentified person at arrival (not in departure crew; e.g. from another boat)."""

    note: str = "This individual does not match any registered crew from this trip's departure."


class ArrivalCrewCheckResponse(BaseModel):
    """Result of arrival crew scan: annotated_image_url + counts + present/missing/unidentified lists."""

    movement_id: str
    boat_id: str
    annotated_image_url: Optional[str] = None
    crew_at_departure: int
    crew_at_arrival: int  # number identified (present) in scan
    missing_crew_count: int
    unidentified_count: int
    present_crew: List[ArrivalCrewMemberStatus]
    missing_crew: List[ArrivalCrewMemberStatus]
    unidentified_crew: List[ArrivalUnidentifiedEntry]  # one entry per unidentified face (or summary count)


class ArrivalInventoryItemCreate(BaseModel):
    """Arrival quantities for one category (officer fills after counting at arrival)."""

    diesel_liters: Optional[float] = None
    ice_blocks: Optional[int] = None
    fishing_net_count: Optional[int] = None
    plastic_bottle_count: Optional[int] = None
    plastic_bag_count: Optional[int] = None


InventoryLossReason = Literal["consumed", "lost_at_sea", "left_at_port", "theft", "other"]


class ArrivalInventoryItemDiscrepancy(BaseModel):
    """One inventory line with departure vs arrival and optional reason for loss."""

    item_name: str  # e.g. "diesel_liters", "fishing_net_count"
    departure_quantity: Optional[float] = None  # int for counts
    arrival_quantity: Optional[float] = None
    status: Literal["matched", "missing"]  # missing = departure > arrival
    reason_for_loss: Optional[InventoryLossReason] = None
    additional_details: Optional[str] = None


class LossReasonEntry(BaseModel):
    """Reason for inventory loss (for missing items)."""

    reason: InventoryLossReason
    additional_details: Optional[str] = None


class ArrivalInventoryCheckRequest(BaseModel):
    """Arrival inventory counts from officer + optional image_url and per-item loss reasons."""

    diesel_liters: Optional[float] = None
    ice_blocks: Optional[int] = None
    fishing_net_count: Optional[int] = None
    plastic_bottle_count: Optional[int] = None
    plastic_bag_count: Optional[int] = None
    image_url: Optional[str] = None
    loss_reasons: Optional[Dict[str, LossReasonEntry]] = None  # key = item_name e.g. "fishing_net_count"


class InventoryCategorySummary(BaseModel):
    """Summary for one inventory category (departure vs arrival)."""

    departure: int
    arrival: int
    status: Literal["matched", "missing"]
    verified: bool  # True when status is matched


class ArrivalInventoryCheckSummary(BaseModel):
    """Check summary for fishing nets and plastic items (bottles + bags)."""

    fishing_nets: InventoryCategorySummary
    plastic_items: InventoryCategorySummary


class ArrivalInventoryCheckResponse(BaseModel):
    """Comparison of departure vs arrival inventory with matched/missing and reasons."""

    movement_id: str
    boat_id: str
    image_url: Optional[str] = None
    items: List[ArrivalInventoryItemDiscrepancy]
    all_matched: bool
    summary: Optional[ArrivalInventoryCheckSummary] = None


# ----- Movement history (for History screens) -----

HistoryDateFilter = Literal["today", "last_7_days", "last_30_days"]


class BoatMovementHistoryItem(BaseModel):
    """One movement entry for history listing (e.g. Departure History)."""

    movement_id: str
    boat_id: str
    boat_number: str
    boat_name: Optional[str] = None
    movement_at: datetime


class BoatMovementHistoryResponse(BaseModel):
    """History response containing movements for a given type and date filter."""

    movement_type: Literal["departure", "arrival", "partial_arrival"]
    date_filter: HistoryDateFilter
    total_records: int
    records: List[BoatMovementHistoryItem]
