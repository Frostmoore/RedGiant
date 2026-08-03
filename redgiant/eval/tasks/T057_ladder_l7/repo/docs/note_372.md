# Service note 372

Service gemini: the retention_days is 720.
Service sagitta: the retention_days is 851.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Configuration lives in the central repository and is applied by CI.
Backups are taken hourly and pruned by the retention policy.
