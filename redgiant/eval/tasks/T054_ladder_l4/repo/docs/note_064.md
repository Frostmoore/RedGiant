# Service note 064

Service lyra: the max_connections is 922.
Service cygnus: the cache_size_mb is 153.

The service exposes Prometheus metrics on the standard admin path.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
