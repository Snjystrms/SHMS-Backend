"""Schemas for buyer deliveries (auctions won by the buyer)."""

from datetime import datetime
from typing import List
from typing import Optional

from pydantic import BaseModel


class DeliveryListItem(BaseModel):
    """Delivery item for list view - auction won by buyer."""

    delivery_id: str
    auction_identifier: str
    location: str
    status: str
    fish_type: str
    bid_price: float
    auction_type: str
    start_time: str
    my_bid: float
    required_quantity: float
    delivered_quantity: float
    delivery_status: str
    delivered_at: Optional[datetime] = None


class DeliveryListResponse(BaseModel):
    """Response for list of buyer deliveries."""

    deliveries: List[DeliveryListItem]


class DeliveryDetail(BaseModel):
    """Delivery detail for QR screen - extends list item with buyer name and QR payload."""

    delivery_id: str
    auction_identifier: str
    location: str
    status: str
    fish_type: str
    bid_price: float
    auction_type: str
    start_time: str
    my_bid: float
    required_quantity: float
    delivered_quantity: float
    delivery_status: str
    delivered_at: Optional[datetime] = None
    buyer_name: str
    qr_payload: str
