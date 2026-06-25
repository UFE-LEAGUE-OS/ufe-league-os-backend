# 09. Flutterwave Payment Flows

This backend currently uses Flutterwave for:

1. Sponsorship payments.
2. Match ticket payments under FAN-004.

## Important Principle

The frontend must never be the source of truth for payment success.

Correct rule:

```text
Only the backend can confirm payment after verifying the transaction with Flutterwave.
```

## Shared Flutterwave Settings

```env
FLUTTERWAVE_MODE=test
FLUTTERWAVE_BASE_URL=https://api.flutterwave.com/v3
FLUTTERWAVE_PUBLIC_KEY=FLWPUBK_TEST-your-test-public-key
FLUTTERWAVE_SECRET_KEY=FLWSECK_TEST-your-test-secret-key
FLUTTERWAVE_SECRET_HASH=replace-with-random-test-webhook-secret
FLUTTERWAVE_TIMEOUT_SECONDS=30
```

## Sponsorship Payment Flow

```text
Sponsor agreement created
       |
       v
POST /api/sponsorships/agreements/<agreement_id>/flutterwave/initialize/
       |
       v
Backend calls Flutterwave /payments
       |
       v
Frontend/user opens checkout_url
       |
       v
Flutterwave redirects to /api/sponsorships/flutterwave/verify/
       |
       v
Backend verifies transaction
       |
       v
Backend confirms or rejects sponsorship payment
```

Sponsorship redirect:

```env
FLUTTERWAVE_REDIRECT_URL=http://localhost:8000/api/sponsorships/flutterwave/verify/
```

## Ticket Payment Flow

```text
Fan selects match ticket type
       |
       v
POST /api/ticketing/orders/flutterwave/initialize/
       |
       v
Backend creates TicketOrder as PENDING
       |
       v
Backend creates TicketOrderItem
       |
       v
Backend calls Flutterwave /payments
       |
       v
Frontend/user opens checkout_url
       |
       v
Flutterwave redirects to /api/ticketing/flutterwave/verify/
       |
       v
Backend verifies transaction
       |
       v
Backend marks TicketOrder as PAID
       |
       v
Backend issues Ticket records
```

Ticketing redirect:

```env
FLUTTERWAVE_TICKET_REDIRECT_URL=http://localhost:8000/api/ticketing/flutterwave/verify/
```

## FAN-004 Ticketing Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/ticketing/matches/<match_id>/ticket-types/` | List available ticket types. |
| `POST` | `/api/ticketing/orders/flutterwave/initialize/` | Create order and initialize checkout. |
| `GET` | `/api/ticketing/flutterwave/verify/?tx_ref=...` | Verify payment and issue tickets. |
| `POST` | `/api/ticketing/flutterwave/webhook/` | Receive payment webhook. |
| `GET` | `/api/ticketing/tickets/me/` | Fan's issued tickets. |
| `POST` | `/api/ticketing/validate/` | Ticket check-in. |

## Why Tickets Are Not Created at Checkout

Checkout initialization does not mean payment has happened.

At checkout initialization:

- `TicketOrder` is created.
- `TicketOrderItem` is created.
- Flutterwave checkout URL is returned.
- No `Ticket` record is created yet.

After successful backend verification:

- `TicketOrder.status` becomes `PAID`.
- `Ticket` records are created.
- `TicketType.quantity_sold` is increased.

## Idempotency

Payment providers can send repeated redirects or webhooks.

Ticket verification must be idempotent:

```text
Verifying the same paid order twice must not create duplicate tickets.
```

The ticketing service checks if the order is already paid and returns existing tickets.

## Webhook Security

Flutterwave webhooks should be checked with `FLUTTERWAVE_SECRET_HASH`.

If the secret hash is configured:

- Invalid signatures return `403`.
- Valid signatures continue to verification.

## Test Mode

Use Flutterwave test keys in development and staging. Do not use production keys until the client/platform owner has approved production payments.

## Common Payment Failure Reasons

| Symptom | Likely Cause |
|---|---|
| Checkout initialization returns 502 | Flutterwave key/base URL/network error. |
| Verification fails | Transaction status not successful. |
| Amount mismatch | Frontend/order amount does not match Flutterwave amount. |
| Currency mismatch | Order currency differs from Flutterwave response. |
| Reference mismatch | `tx_ref` does not match order `payment_reference`. |
| Webhook rejected | Missing or wrong webhook secret hash. |
