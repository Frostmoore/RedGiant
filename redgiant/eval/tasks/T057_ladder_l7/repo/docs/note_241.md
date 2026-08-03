# Service note 241

Service vela: the cache_size_mb is 328.
Service hydra: the cache_size_mb is 207.

The runbook documents the failover procedure in detail.
The service exposes Prometheus metrics on the standard admin path.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
