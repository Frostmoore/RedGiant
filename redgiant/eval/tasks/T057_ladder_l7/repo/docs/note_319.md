# Service note 319

Service gemini: the retention_days is 793.
Service atlas: the worker_count is 252.

The service exposes Prometheus metrics on the standard admin path.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The runbook documents the failover procedure in detail.
