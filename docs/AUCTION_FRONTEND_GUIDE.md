# Auction API – Frontend Integration Guide

This guide describes how to integrate the frontend with the **Auction** and **Live Bidding (WebSocket)** APIs.

**Base URL:** `https://your-api-host/api/v1` (e.g. `http://localhost:8000/api/v1`)

---

## Authentication

- **Create auction:** requires **Boat Owner** or **Agent** login. Use the user's token in the `Authorization` header.
- **List auctions / Get auction:** no auth required (public).
- **Place bid:** requires any **logged-in user**. Use the user's JWT in the `Authorization` header.

```
Authorization: Bearer <access_token>
```

---

## HTTP Endpoints

### 1. Create auction (Boat Owner or Agent)

**POST** `/api/v1/auctions`

Creates a new fish auction with initial price and schedule. Exactly one of `movement_id` or `bidding_request_id` must be provided.

- **Boat owner self auction:** Provide `movement_id` (latest movement of their boat from the boat status API).
- **Agent auction:** Provide `bidding_request_id` (approved bidding request only).

**Headers:** `Authorization: Bearer <boat_owner_or_agent_token>`  
**Content-Type:** `application/json`

**Request body (boat owner self auction):**

```json
{
  "fish_name": "Tuna",
  "initial_price": 100.50,
  "start_time": "2026-02-25T10:00:00Z",
  "auction_type": "open_box",
  "movement_id": "uuid-of-latest-movement",
  "bidding_request_id": null
}
```

**Request body (agent auction):**

```json
{
  "fish_name": "Tuna",
  "initial_price": 100.50,
  "start_time": "2026-02-25T10:00:00Z",
  "auction_type": "open_box",
  "movement_id": null,
  "bidding_request_id": "uuid-of-approved-request"
}
```

| Field               | Type     | Required | Description                                                |
|---------------------|----------|----------|------------------------------------------------------------|
| `fish_name`         | string   | Yes      | Name or type of fish                                       |
| `initial_price`    | number   | Yes      | Starting price (must be > 0)                                |
| `start_time`        | datetime | Yes      | When the auction becomes active (ISO 8601)                  |
| `auction_type`      | string   | No       | `open_box` or `dutch` (default: `open_box`)                 |
| `movement_id`       | string   | One of   | Boat owner self auction: latest movement id of their boat   |
| `bidding_request_id`| string   | One of   | Agent auction: approved bidding request id                  |

Note: `end_time` is not required. When omitted, it defaults to `start_time` + 24 hours.

**Success (201):**

```json
{
  "id": "uuid",
  "seller_id": "uuid",
  "fish_name": "Tuna",
  "initial_price": 100.5,
  "current_price": 100.5,
  "start_time": "2026-02-25T10:00:00Z",
  "end_time": "2026-02-25T18:00:00Z",
  "status": "scheduled",
  "winner_id": null,
  "bidding_request_id": null,
  "movement_id": "uuid",
  "auction_type": "open_box"
}
```

**Errors:** `400` (invalid data, missing or invalid movement_id/bidding_request_id), `401` (unauthorized), `403` (not boat owner or agent).

---

### 2. List all auctions

**GET** `/api/v1/auctions/active`

Returns **all** auctions (active and non-active), newest first. No auth required.

**Success (200):**

```json
[
  {
    "id": "uuid",
    "seller_id": "uuid",
    "fish_name": "Tuna",
    "initial_price": 100.5,
    "current_price": 150.0,
    "start_time": "2026-02-25T10:00:00Z",
    "end_time": "2026-02-25T18:00:00Z",
    "status": "active",
    "winner_id": null
  }
]
```

---

### 3. Get one auction

**GET** `/api/v1/auctions/{auction_id}`

Returns a single auction by ID. No auth required.

**Success (200):** Same shape as one object in the list above.

**Errors:** `404` if auction not found.

---

### 4. Place a bid

**POST** `/api/v1/auctions/{auction_id}/bids`

Places a bid on an auction. The bid is saved and **broadcast to all clients** watching that auction via WebSocket.

**Headers:** `Authorization: Bearer <user_token>`  
**Content-Type:** `application/json`

**Request body:**

```json
{
  "amount": 120.00,
  "quantity": 50
}
```

| Field     | Type   | Required | Description                                  |
|----------|--------|----------|----------------------------------------------|
| `amount` | number | Yes      | Bid amount; must be **greater than** current price |
| `quantity` | number | Yes    | Quantity being bid for (must be > 0)         |

**Success (200):**

```json
{
  "id": "uuid",
  "auction_id": "uuid",
  "bidder_id": "uuid",
  "amount": 120.0,
  "quantity": 50,
  "created_at": "2026-02-25T12:30:00Z"
}
```

**Errors:** `400` (invalid amount, auction not open for bidding, or outside time window), `401` (unauthorized), `404` (auction not found).

---

## WebSocket – Live bid updates

When a user places a bid, **every client** watching that auction receives the new bid in real time over a WebSocket connection.

### WebSocket URL

```
ws://<host>/api/v1/ws/auctions/{auction_id}
```

Example: `ws://localhost:8000/api/v1/ws/auctions/abc-123-uuid`

- Replace `http` with `ws` (and `https` with `wss` in production).
- No query params or auth are required for the current implementation.

### Flow

1. User opens the auction detail page → frontend opens a WebSocket to the URL above.
2. Keep the connection open while the user is on the page.
3. When **any** user places a bid on this auction, the server sends a JSON message to all connected clients.
4. On message received, update the UI (current price, last bidder, bid history, etc.).
5. On leaving the page, close the WebSocket.

### Message from server (when someone bids)

The server **sends** (you only listen; no need to send messages for live updates):

```json
{
  "type": "new_bid",
  "auction_id": "uuid",
  "amount": 120.0,
  "bidder_id": "uuid",
  "created_at": "2026-02-25T12:30:00.000Z"
}
```

| Field        | Type   | Description                    |
|-------------|--------|--------------------------------|
| `type`      | string | Always `"new_bid"`             |
| `auction_id`| string | Auction UUID                   |
| `amount`    | number | New bid amount                 |
| `bidder_id` | string | User ID of the bidder          |
| `created_at`| string | ISO 8601 timestamp of the bid  |

### Example (JavaScript)

```javascript
const auctionId = "your-auction-uuid";
const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/ws/auctions/${auctionId}`;
const ws = new WebSocket(wsUrl);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === "new_bid") {
    // Update UI: current price, last bidder, add to bid list
    console.log("New bid:", data.amount, "by", data.bidder_id);
  }
};

ws.onclose = () => console.log("Auction live connection closed");
ws.onerror = (err) => console.error("WebSocket error", err);

// When leaving the page:
// ws.close();
```

---

## Auction status values

| Status       | Description                                      |
|-------------|---------------------------------------------------|
| `scheduled` | Not yet started (before `start_time`)             |
| `active`    | Open for bidding (`start_time` ≤ now &lt; `end_time`) |
| `completed` | Ended (`end_time` passed)                         |
| `cancelled` | Cancelled                                        |

Use `status` and `start_time` / `end_time` to show labels like “Upcoming”, “Live”, “Ended” and to enable/disable the bid button.

---

## Quick reference

| Action           | Method | Endpoint                              | Auth        |
|-----------------|--------|---------------------------------------|-------------|
| Create auction  | POST   | `/api/v1/auctions`                    | Boat owner or Agent |
| List all auctions | GET  | `/api/v1/auctions/active`             | None        |
| Get one auction | GET    | `/api/v1/auctions/{id}`              | None        |
| Place bid       | POST   | `/api/v1/auctions/{id}/bids`          | Any user    |
| Live bid updates| WebSocket | `ws://host/api/v1/ws/auctions/{id}` | None (optional later) |
