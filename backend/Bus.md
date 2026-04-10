# SmartDalali “System Bus” (SAFE Celery Event Layer)

This project does **not** have a full message bus (Kafka/Rabbit) for domain correctness.
Instead, it uses a **safe, non-breaking, Celery-backed event dispatcher** to run **side effects only** (notifications, analytics, integrations).

## Where it is implemented

- **Emit API (call sites use this):** `backend/core/events.py` → `emit_event(event_name, payload)`
- **Async transport (Celery task):** `backend/core/tasks.py` → `dispatch_event_task`
- **Handler registry (worker-side):** `backend/core/event_handlers.py` → `handle_event(...)` and per-event handler functions

## How it works (end-to-end flow)

1. Business logic completes synchronously (order lifecycle, escrow payment confirmation, etc.).
2. Code emits an event: `emit_event("ORDER_COMPLETED", {"order_id": ...})`.
3. `emit_event`:
   - **logs** `[EVENT] ...` at INFO (for observability)
   - normalizes payload to be **JSON-safe** (Celery uses JSON serializer)
   - enqueues `dispatch_event_task.delay(event_name, payload)`
   - **swallows errors** if broker is down (system remains functional)
4. Celery worker runs `dispatch_event_task`, which calls `handle_event(event_name, payload)`.
5. `handle_event` routes to a specific handler (e.g., `handle_order_completed`) which performs **side effects only**.

## Safety rules (critical)

- **No domain correctness depends on events.**
- **Do not move** financial / escrow logic into event handlers.
- **Do not move** order lifecycle transitions into event handlers.
- Event handlers are for **side effects** only.

## Key snippets

### 1) Emission (sync log + async enqueue)

```py
from core.events import emit_event

emit_event("ORDER_COMPLETED", {"order_id": order.id})
```

### 2) Celery dispatch task (transport)

```py
@shared_task(...)
def dispatch_event_task(self, event_name, payload):
    from core.event_handlers import handle_event
    handle_event(event_name, payload or {})
```

### 3) Handler registry (safe routing)

```py
def handle_event(event_name: str, payload: dict):
    if event_name == "ORDER_COMPLETED":
        handle_order_completed(payload)
    elif event_name == "PAYMENT_CONFIRMED":
        handle_payment_confirmed(payload)
    # extend safely
```

## Common event names emitted today

- `ORDER_CREATED`
- `ORDER_CONFIRMED`
- `ORDER_SHIPPED`
- `ORDER_DELIVERED`
- `ORDER_COMPLETED`
- `ORDER_CANCELLED`
- `PAYMENT_CONFIRMED`
- `ESCROW_FUNDS_RELEASED`
- `ESCROW_REFUND_APPLIED`
- `ORDER_DISPUTE_OPENED`
- `ORDER_DISPUTE_RESOLVED`

## Operational notes

- Celery configuration uses `app.autodiscover_tasks()`, so `core.tasks` is discovered because `core` is in `INSTALLED_APPS`.
- If Celery/Redis is down, events still **log** but handlers won’t run until the broker is available again.

