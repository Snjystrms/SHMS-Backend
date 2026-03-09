"""Schemas for agent dashboard."""

from typing import List

from pydantic import BaseModel


class AgentArrivedBoatItem(BaseModel):
    boat_id: str
    boat_number: str
    boat_name: str
    boat_status: str
    time: str


class AgentDashboardResponse(BaseModel):
    arrived_boats_count: int
    arrived_boats: List[AgentArrivedBoatItem]

