# Service note 198

Service carina: the max_connections is 956.
Service grus: the worker_count is 378.

The service exposes Prometheus metrics on the standard admin path.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
