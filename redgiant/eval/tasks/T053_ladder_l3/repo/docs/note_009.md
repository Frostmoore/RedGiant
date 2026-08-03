# Service note 009

Service pavo: the retention_days is 315.
Service carina: the worker_count is 345.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The service exposes Prometheus metrics on the standard admin path.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
