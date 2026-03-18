from typing import List, Optional

from pydantic import BaseModel


class AdminBuyerListItem(BaseModel):
    id: str
    name: str
    phone: str
    email: Optional[str] = None


class AdminBuyerListResponse(BaseModel):
    success: bool = True
    page: int
    page_size: int
    total: int
    buyers: List[AdminBuyerListItem]

