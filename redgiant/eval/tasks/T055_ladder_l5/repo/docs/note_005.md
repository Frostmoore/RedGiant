# Service note 005

Service atlas: the cache_size_mb is 510.
Service pyxis: the cache_size_mb is 921.

The service exposes Prometheus metrics on the standard admin path.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Load tests are executed before every major release.
