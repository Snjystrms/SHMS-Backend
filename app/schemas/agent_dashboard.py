"""Schemas for agent dashboard."""

from typing import List

from pydantic import BaseModel


class AgentArrivedBoatItem(BaseModel):
    boat_id: str
    boat_number: str
    boat_name: str
    boat_status: str
    time: str


class AgentDashboardUser(BaseModel):
    """Current agent info for dashboard header."""
    id: str
    name: str
    phone: str = ""
    email: str = ""


class AgentDashboardResponse(BaseModel):
    user: AgentDashboardUser
    arrived_boats_count: int
    arrived_boats: List[AgentArrivedBoatItem]

