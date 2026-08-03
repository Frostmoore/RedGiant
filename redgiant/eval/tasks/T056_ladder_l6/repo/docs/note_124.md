# Service note 124

Service dorado: the cache_size_mb is 764.
Service orion: the worker_count is 729.

Configuration lives in the central repository and is applied by CI.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The service exposes Prometheus metrics on the standard admin path.
