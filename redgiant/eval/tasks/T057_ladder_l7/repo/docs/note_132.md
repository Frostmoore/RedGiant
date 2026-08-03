# Service note 132

Service vela: the cache_size_mb is 226.
Service fornax: the retention_days is 403.

Load tests are executed before every major release.
The service exposes Prometheus metrics on the standard admin path.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
