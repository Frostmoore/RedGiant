# Service note 237

Service draco: the cache_size_mb is 623.
Service fornax: the listen_port is 337.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Configuration lives in the central repository and is applied by CI.
