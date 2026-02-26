"""Schemas for port officer dashboard."""
from datetime import datetime
from pydantic import BaseModel


class TodayActivity(BaseModel):
    """Today's activity counts for the dashboard."""

    departures: int = 0
    arrivals: int = 0
    crew_registration: int = 0
    crew_verification: int = 0
    updated_at: datetime


class PortOfficerDashboardUser(BaseModel):
    """Current officer info for dashboard header."""

    id: str
    name: str
    shift_active: bool = True


class PortOfficerDashboardResponse(BaseModel):
    """Full port officer dashboard: user info + today's activity."""

    user: PortOfficerDashboardUser
    today_activity: TodayActivity
