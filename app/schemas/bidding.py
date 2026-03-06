"""Schemas for agent bidding requests."""

from typing import Optional, List
from pydantic import BaseModel


class BiddingRequestCreate(BaseModel):
    boat_id: str
    note: Optional[str] = None


class BiddingRequestItem(BaseModel):
    id: str
    boat_id: str
    boat_number: str
    boat_name: str
    agent_id: str
    agent_name: str
    status: str
    note: Optional[str] = None
    created_at: str


class BiddingRequestResponse(BaseModel):
    success: bool
    message: str
    bidding_request: Optional[BiddingRequestItem] = None


class BiddingRequestListResponse(BaseModel):
    success: bool
    total: int
    bidding_requests: List[BiddingRequestItem]


class BiddingRequestAction(BaseModel):
    status: str  # "approved" or "rejected"
