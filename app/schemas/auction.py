from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


AuctionStatus = Literal["scheduled", "active", "completed", "cancelled"]


class AuctionCreate(BaseModel):
    """Request body to create a new auction for fish."""

    fish_name: str = Field(..., description="Name or type of fish being auctioned")
    initial_price: float = Field(..., gt=0, description="Starting price for the auction")
    start_time: datetime = Field(..., description="When the auction becomes active")
    end_time: datetime = Field(..., description="When the auction ends")


class Auction(BaseModel):
    """Auction details returned to clients."""

    id: str
    seller_id: str
    fish_name: str
    initial_price: float
    current_price: float
    start_time: datetime
    end_time: datetime
    status: AuctionStatus
    winner_id: Optional[str] = None

    class Config:
        from_attributes = True


class AuctionUpdate(BaseModel):
    """Fields that seller can update on an existing auction."""

    fish_name: Optional[str] = Field(None, description="Updated fish name or type")
    start_time: Optional[datetime] = Field(None, description="Updated auction start time")
    end_time: Optional[datetime] = Field(None, description="Updated auction end time")


class BidCreate(BaseModel):
    """Payload when a user places a bid on an auction."""

    amount: float = Field(..., gt=0, description="Bid amount (must be higher than current price)")


class Bid(BaseModel):
    """Bid details returned to clients."""

    id: str
    auction_id: str
    bidder_id: str
    amount: float
    created_at: datetime
    bidder_name: Optional[str] = None

    class Config:
        from_attributes = True

