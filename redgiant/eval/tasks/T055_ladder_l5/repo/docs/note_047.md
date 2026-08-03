# Service note 047

Service atlas: the retention_days is 505.
Service volans: the retention_days is 915.

Backups are taken hourly and pruned by the retention policy.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Configuration lives in the central repository and is applied by CI.
