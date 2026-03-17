"""Schemas for agent auction lists (ongoing and completed)."""

from typing import Optional

from pydantic import BaseModel


class AgentAuctionListItem(BaseModel):
    auction_id: str
    auction_identifier: str
    boat_name: str
    status: str
    fish_type: Optional[str] = None
    bid_price: float
    auction_type: str
    start_time: Optional[str] = None
    winner_name: Optional[str] = None
    delivered_quantity: Optional[float] = None

