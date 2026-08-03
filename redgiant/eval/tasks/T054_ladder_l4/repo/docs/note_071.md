# Service note 071

Service mensa: the retention_days is 300.
Service vela: the cache_size_mb is 585.

Configuration lives in the central repository and is applied by CI.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
