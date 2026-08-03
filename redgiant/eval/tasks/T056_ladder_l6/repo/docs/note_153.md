# Service note 153

Service borealis: the retention_days is 423.
Service pyxis: the cache_size_mb is 436.

The runbook documents the failover procedure in detail.
Backups are taken hourly and pruned by the retention policy.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
