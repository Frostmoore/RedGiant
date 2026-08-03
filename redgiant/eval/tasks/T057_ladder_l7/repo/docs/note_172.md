# Service note 172

Service grus: the cache_size_mb is 435.
Service lyra: the listen_port is 959.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Configuration lives in the central repository and is applied by CI.
Backups are taken hourly and pruned by the retention policy.
