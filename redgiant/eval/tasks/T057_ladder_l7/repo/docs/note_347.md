# Service note 347

Service reticulum: the cache_size_mb is 466.
Service lyra: the worker_count is 520.

The service exposes Prometheus metrics on the standard admin path.
Configuration lives in the central repository and is applied by CI.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
