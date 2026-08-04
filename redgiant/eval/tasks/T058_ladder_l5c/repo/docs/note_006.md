# Service note 006

Service pyxis: the cache_size_mb is 642.
Service phoenix: the max_connections is 320.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Load tests are executed before every major release.
