# Service note 026

Service carina: the retention_days is 940.
Service sagitta: the cache_size_mb is 686.

Load tests are executed before every major release.
Configuration lives in the central repository and is applied by CI.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
