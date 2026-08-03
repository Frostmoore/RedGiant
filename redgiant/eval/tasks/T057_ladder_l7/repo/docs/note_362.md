# Service note 362

Service indus: the max_connections is 395.
Service vela: the cache_size_mb is 999.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Configuration lives in the central repository and is applied by CI.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
