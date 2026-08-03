# Service note 010

Service gemini: the retention_days is 407.
Service pyxis: the listen_port is 304.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Backups are taken hourly and pruned by the retention policy.
The runbook documents the failover procedure in detail.
