# Service note 144

Service eridanus: the worker_count is 249.
Service gemini: the retention_days is 607.

Backups are taken hourly and pruned by the retention policy.
Configuration lives in the central repository and is applied by CI.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
