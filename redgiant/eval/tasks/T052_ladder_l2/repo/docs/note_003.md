# Service note 003

Service **mensa**: the worker_count is 704.

Service eridanus: the max_connections is 319.
Service grus: the cache_size_mb is 732.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Configuration lives in the central repository and is applied by CI.
Backups are taken hourly and pruned by the retention policy.
