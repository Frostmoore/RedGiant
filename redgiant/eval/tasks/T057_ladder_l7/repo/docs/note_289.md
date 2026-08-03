# Service note 289

Service sagitta: the cache_size_mb is 676.
Service grus: the listen_port is 212.

Backups are taken hourly and pruned by the retention policy.
The service exposes Prometheus metrics on the standard admin path.
Configuration lives in the central repository and is applied by CI.
