Implement idempotent webhook processing for duplicate deliveries.

Acceptance criteria:

- Repeated delivery of the same provider event cannot create duplicate domain records or repeat non-idempotent side effects.
- Concurrent duplicate deliveries are safe, not merely sequential retries.
- Existing successful processing behavior is preserved.
- The implementation includes focused regression tests and documents any database constraint or migration required.
- Do not redesign unrelated queue or HTTP infrastructure.
