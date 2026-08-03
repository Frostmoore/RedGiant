# Service note 032

Service phoenix: the max_connections is 476.

Service pavo: the cache_size_mb is 492.
Service hydra: the max_connections is 778.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Configuration lives in the central repository and is applied by CI.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
