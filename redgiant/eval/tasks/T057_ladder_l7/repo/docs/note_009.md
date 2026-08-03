# Service note 009

Service aquila: the cache_size_mb is 675.
Service eridanus: the listen_port is 445.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Backups are taken hourly and pruned by the retention policy.
Load tests are executed before every major release.
