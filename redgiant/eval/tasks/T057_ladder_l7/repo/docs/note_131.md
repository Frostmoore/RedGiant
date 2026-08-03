# Service note 131

Service draco: the worker_count is 581.
Service cygnus: the max_connections is 250.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The service exposes Prometheus metrics on the standard admin path.
