"""Schemas for boat owner sales report."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

SalesReportFilter = Literal[
    "last_auction",
    "last_week",
    "last_month",
    "last_three_months",
    "last_year",
    "custom",
]


class SalesReportFilterApplied(BaseModel):
    filter: SalesReportFilter
    from_date: Optional[date] = None
    to_date: Optional[date] = None


class BoatOwnerSalesReportItem(BaseModel):
    auction_id: str
    auction_identifier: str
    boat_number: Optional[str] = None
    fish_type: Optional[str] = None
    auction_type: Optional[str] = None
    delivered_at: Optional[datetime] = None
    sale: float = Field(..., ge=0)


class BoatOwnerSalesReportResponse(BaseModel):
    success: bool = True
    total_earning: float = 0.0
    total_records: int = 0
    filter_applied: SalesReportFilterApplied
    records: List[BoatOwnerSalesReportItem] = []

