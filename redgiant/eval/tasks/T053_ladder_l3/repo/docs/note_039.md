# Service note 039

Service **phoenix**: the listen_port is 796.

Service fornax: the cache_size_mb is 972.
Service pavo: the cache_size_mb is 167.

The runbook documents the failover procedure in detail.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Backups are taken hourly and pruned by the retention policy.
