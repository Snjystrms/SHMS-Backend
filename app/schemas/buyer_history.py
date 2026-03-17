"""Schemas for buyer history (auction history and delivery history)."""

from datetime import datetime
from typing import List
from typing import Optional

from pydantic import BaseModel


class AuctionHistoryItem(BaseModel):
    """Auction history item - won auction with Bid Won status."""

    auction_id: str
    auction_identifier: str
    description: str
    status: str
    fish_type: str
    bid_price: float
    auction_type: str
    start_time: str
    my_bid: float
    required_quantity: float


class AuctionHistoryResponse(BaseModel):
    """Response for auction history list."""

    auctions: List[AuctionHistoryItem]


class DeliveryHistoryItem(BaseModel):
    """Delivery history item - won auction with Delivery Completed status."""

    delivery_id: str
    auction_identifier: str
    description: str
    status: str
    my_bid: float
    required_quantity: float
    delivered_quantity: float
    delivery_status: Optional[str] = None
    delivered_at: Optional[datetime] = None


class DeliveryHistoryResponse(BaseModel):
    """Response for delivery history list."""

    deliveries: List[DeliveryHistoryItem]
