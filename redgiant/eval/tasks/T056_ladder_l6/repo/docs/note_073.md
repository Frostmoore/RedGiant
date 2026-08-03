# Service note 073

Service reticulum: the retention_days is 998.
Service gemini: the retention_days is 812.

The runbook documents the failover procedure in detail.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Backups are taken hourly and pruned by the retention policy.
