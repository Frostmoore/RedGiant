# Service note 037

Service draco: the worker_count is 835.
Service reticulum: the max_connections is 846.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Configuration lives in the central repository and is applied by CI.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
