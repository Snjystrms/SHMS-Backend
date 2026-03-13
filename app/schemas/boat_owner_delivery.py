"""Schemas for boat owner delivery (scan QR and record delivery)."""

from typing import Optional

from pydantic import BaseModel, Field


class ScanDeliveryRequest(BaseModel):
    """Request body for scanning QR payload. Accept either qr_payload or auction_id+buyer_id."""

    auction_id: Optional[str] = Field(None, description="Auction ID from QR")
    buyer_id: Optional[str] = Field(None, description="Buyer ID from QR")
    qr_payload: Optional[str] = Field(None, description="Raw JSON string from QR: {\"auction_id\":\"...\",\"buyer_id\":\"...\"}")


class ScanDeliveryResponse(BaseModel):
    """Response for delivery scan - buyer and auction details for boat owner."""

    auction_id: str
    buyer_name: str
    bid_price: float
    auction_type: str
    requested_quantity: float
    delivered_quantity: float
    fish_type: str
    start_time: str
    auction_identifier: str
    is_already_delivered: bool


class InitiateDeliveryResponse(BaseModel):
    """Response for boat owner initiate delivery screen (post-auction)."""

    auction_id: str
    buyer_name: str
    bid_price: float
    auction_type: str
    requested_quantity: float
    delivered_quantity: float
    fish_type: str
    start_time: str
    auction_identifier: str
    is_already_delivered: bool


class RecordDeliveryRequest(BaseModel):
    """Request body for recording delivered quantity."""

    delivered_quantity: float = Field(..., gt=0, description="Quantity delivered in KG")


class RecordDeliveryResponse(BaseModel):
    """Response for recording delivery."""

    success: bool
    message: str


class PendingDeliveryItem(BaseModel):
    """One pending delivery card item for boat owner."""

    auction_id: str
    auction_identifier: str
    fish_type: str
    auction_type: str
    bid_price: float
    requested_quantity: float
    delivered_quantity: float
    start_time: str
    status: str
