"""Schemas for buyer dashboard."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class BuyerDashboardUser(BaseModel):
    """Current buyer info for dashboard header."""

    id: str
    name: str


class LiveAuctionItem(BaseModel):
    """Live auction item with buyer's bid for dashboard."""

    auction_id: str
    auction_identifier: str
    item_title: str
    status: str
    fish_type: str
    current_bid_price: float
    auction_type: str
    start_time: str
    my_bid: Optional[float] = None
    required_quantity: Optional[str] = None


class BuyerDashboardResponse(BaseModel):
    user: BuyerDashboardUser
    total_bids: int
    pending_delivery: int
    live_auctions: List[LiveAuctionItem]
    updated_at: datetime
