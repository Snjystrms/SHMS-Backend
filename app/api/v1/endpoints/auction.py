from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
from app.schemas.auction import Auction, AuctionCreate, AuctionUpdate, Bid, BidCreate
from app.services import auction_service

router = APIRouter()


@router.post(
    "/auctions",
    response_model=Auction,
    status_code=status.HTTP_201_CREATED,
)
async def create_auction(
    auction_in: AuctionCreate,
    current_user: dict = Depends(deps.get_boat_owner_or_agent_user),
):
    """
    Create a new auction for fish.
    - Boat owner self auction: provide movement_id (latest movement of their boat).
    - Agent auction: provide bidding_request_id (approved request only).
    """
    auction, err = auction_service.create_auction(
        caller_id=current_user["id"],
        caller_role=current_user["role"],
        fish_name=auction_in.fish_name,
        initial_price=auction_in.initial_price,
        start_time=auction_in.start_time,
        movement_id=auction_in.movement_id,
        bidding_request_id=auction_in.bidding_request_id,
        auction_type=auction_in.auction_type,
    )
    if err or not auction:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err or "Invalid auction data (check times and price).",
        )
    return auction


@router.get("/auctions/active", response_model=List[Auction])
async def list_all_auctions():
    """List all auctions (active and non-active)."""
    auctions = auction_service.list_auctions()
    return auctions


@router.get("/auctions/{auction_id}", response_model=Auction)
async def get_auction(auction_id: str):
    """Get details of one auction."""
    auction = auction_service.get_auction_by_id(auction_id)
    if not auction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Auction not found",
        )
    return auction


@router.put("/auctions/{auction_id}", response_model=Auction)
async def update_auction(
    auction_id: str,
    auction_in: AuctionUpdate,
    current_user: dict = Depends(deps.get_boat_owner_user),
):
    """Update an existing auction (only by its seller)."""
    updated = auction_service.update_auction(
        auction_id=auction_id,
        seller_id=current_user["id"],
        fish_name=auction_in.fish_name,
        start_time=auction_in.start_time,
        bidding_request_id=auction_in.bidding_request_id,
        movement_id=auction_in.movement_id,
        auction_type=auction_in.auction_type,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not update auction (not found, not owner, invalid time/status, or invalid bidding request).",
        )
    return updated


@router.delete("/auctions/{auction_id}")
async def delete_auction(
    auction_id: str,
    current_user: dict = Depends(deps.get_boat_owner_user),
):
    """Delete an auction (only by its seller; not allowed after completion)."""
    ok = auction_service.delete_auction(auction_id, current_user["id"])
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not delete auction (not found, not owner, or already completed).",
        )
    return {"success": True, "message": "Auction deleted"}


@router.post("/auctions/{auction_id}/end", response_model=Auction)
async def end_auction(
    auction_id: str,
    current_user: dict = Depends(deps.get_boat_owner_user),
):
    """
    Manually end an auction:
    - Only the seller (boat owner) can end it.
    - Status becomes 'completed'.
    - winner_id is set to highest bidder if any.
    """
    auction = auction_service.end_auction(auction_id, current_user["id"])
    if not auction:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not end auction (not found or not owner).",
        )
    return auction


@router.post("/auctions/{auction_id}/bids", response_model=Bid)
async def place_bid(
    auction_id: str,
    bid_in: BidCreate,
    current_user: dict = Depends(deps.get_current_user),
):
    """Place a bid on an auction and broadcast it via WebSocket."""
    bid, err = auction_service.create_bid(
        auction_id=auction_id,
        bidder_id=current_user["id"],
        amount=bid_in.amount,
    )
    if err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err,
        )

    await auction_service.broadcast_bid(auction_id, bid)
    return bid


@router.get("/auctions/{auction_id}/bids", response_model=List[Bid])
async def list_bids_for_auction(auction_id: str):
    """List all bids for a specific auction (any status)."""
    bids = auction_service.list_bids_for_auction(auction_id)
    return bids

