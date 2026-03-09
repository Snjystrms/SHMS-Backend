"""Schemas for boat owner dashboard."""

from datetime import datetime
from typing import List

from pydantic import BaseModel


class BoatOwnerDashboardUser(BaseModel):
    id: str
    name: str


class QuickActivityTabs(BaseModel):
    total_boats: int = 0
    in_sea: int = 0


class PendingAuctionBoatItem(BaseModel):
    boat_id: str
    boat_number: str
    boat_name: str
    status: str
    arrival_time: str
    pending_bidding_requests_count: int = 0


class BoatOwnerDashboardResponse(BaseModel):
    user: BoatOwnerDashboardUser
    quick_activity: QuickActivityTabs
    pending_auctions: List[PendingAuctionBoatItem]
    updated_at: datetime
