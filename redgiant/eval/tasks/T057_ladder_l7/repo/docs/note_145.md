# Service note 145

Service vela: the max_connections is 526.
Service aquila: the cache_size_mb is 117.

Configuration lives in the central repository and is applied by CI.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Load tests are executed before every major release.
