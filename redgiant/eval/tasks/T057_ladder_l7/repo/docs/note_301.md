# Service note 301

Service gemini: the worker_count is 721.
Service eridanus: the retention_days is 225.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Configuration lives in the central repository and is applied by CI.
Backups are taken hourly and pruned by the retention policy.
