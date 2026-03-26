"""Schemas for boat trip status (departure, arrival, partial arrival)."""
from datetime import datetime
from typing import Optional, Literal, List, Dict
from pydantic import BaseModel, model_validator

TripStatusType = Literal["docked", "sailing", "arrived", "temporary_arrived", "partial_arrival"]

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
    movement_type: Optional[str] = None  # Actual DB value: departure, temporary_departure, arrival, temporary_arrival, partial_arrival
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
    movement_type: Literal["departure", "arrival", "partial_arrival", "temporary_departure", "temporary_arrival"]
    movement_at: datetime
    partial_arrival_reason: Optional[str] = None
    partial_arrival_details: Optional[str] = None
    image_url: Optional[str] = None


class BoatMovementCrewMemberItem(BaseModel):
    """One crew member assigned to a specific trip (boat movement).
    crop_id: optional face crop ID from scan-group-photo; used to show crew image in history."""

    crew_member_id: str
    crop_id: Optional[str] = None


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
    status: Literal["present", "missing"]
    crop_image_url: Optional[str] = None


class ArrivalUnidentifiedEntry(BaseModel):
    """One unidentified person at arrival (not in departure crew; e.g. from another boat)."""

    id: str
    crop_image_url: Optional[str] = None
    matched_crew_member_id: Optional[str] = None
    matched_name: Optional[str] = None
    matched_is_register: Optional[bool] = None
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


class ArrivalCrewSubmitRequest(BaseModel):
    """Submit arrival crew discrepancies (used to notify admin)."""

    missing_crew_ids: List[str] = []
    unidentified_crew_ids: List[str] = []
    report_missing_person: bool = False
    notes: Optional[str] = None
    annotated_image_url: Optional[str] = None


class ArrivalCrewSubmitResponse(BaseModel):
    """Response for arrival crew submit."""

    success: bool = True
    notification_id: Optional[str] = None
    message: str = "Submitted successfully."


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

    item_name: str
    departure_quantity: Optional[float] = None
    arrival_quantity: Optional[float] = None
    status: Literal["matched", "missing"]
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


# ----- Boat owner trip details (At Sea / At Harbour) -----


class TripDetailsInventoryItem(BaseModel):
    """One inventory item for trip details (diesel, ice, nets, plastics)."""

    type: str  # diesel, ice, fishing_nets, plastic_items
    quantity: float
    unit: str  # Liters, Kg, count


class TripDetailsCrewMember(BaseModel):
    """One crew member in trip details."""

    id: str
    name: str
    role: str  # Pilot or Crew


class TripDetailsDeparture(BaseModel):
    """Departure info for trip details."""

    departure_at: datetime
    from_port: str


class TripDetailsArrival(BaseModel):
    """Arrival info for trip details."""

    arrival_at: datetime
    to_port: str


class TripDetailsMissingItem(BaseModel):
    """One missing item at arrival (for At Harbour view)."""

    type: str
    quantity: float


class TripDetailsMissingCrewMember(BaseModel):
    """One missing crew member at arrival."""

    id: str
    name: str


class TripDetailsUnidentifiedCrewMember(BaseModel):
    """One unidentified person at arrival (not in departure crew)."""

    id: str
    crop_image_url: Optional[str] = None
    note: str = "This individual does not match any registered crew from this trip's departure."


class TripDetailsAtSeaResponse(BaseModel):
    """Boat owner trip details when boat is at sea (latest movement is departure)."""

    view_type: Literal["at_sea"] = "at_sea"
    boat_id: str
    boat_number: str
    boat_name: Optional[str] = None
    trip_status: Literal["current_trip"] = "current_trip"
    departure: TripDetailsDeparture
    vessel_type: Optional[str] = None
    total_crew: int = 0
    inventory_list: List[TripDetailsInventoryItem] = []
    crew_members: List[TripDetailsCrewMember] = []


class TripDetailsAtHarbourResponse(BaseModel):
    """Boat owner trip details when boat is at harbour (latest movement is arrival or partial_arrival)."""

    view_type: Literal["at_harbour"] = "at_harbour"
    boat_id: str
    boat_number: str
    boat_name: Optional[str] = None
    trip_status: Literal["arrived"] = "arrived"
    departure: Optional[TripDetailsDeparture] = None
    arrival: Optional[TripDetailsArrival] = None
    vessel_type: Optional[str] = None
    total_crew: int = 0
    list_of_items_while_departure: List[TripDetailsInventoryItem] = []
    list_of_missing_items: List[TripDetailsMissingItem] = []
    missing_crew_members: List[TripDetailsMissingCrewMember] = []
    unidentified_crew_members: List[TripDetailsUnidentifiedCrewMember] = []
    reason_for_loss: Optional[str] = None
    additional_details: Optional[str] = None
    crew_members: List[TripDetailsCrewMember] = []
    partial_arrival_reason: Optional[str] = None
    partial_arrival_details: Optional[str] = None
