# Service note 080

Service volans: the max_connections is 291.
Service atlas: the worker_count is 312.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The service exposes Prometheus metrics on the standard admin path.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
