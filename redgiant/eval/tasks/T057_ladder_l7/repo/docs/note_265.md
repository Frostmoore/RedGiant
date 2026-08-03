# Service note 265

Service aquila: the cache_size_mb is 443.
Service hydra: the max_connections is 525.

Load tests are executed before every major release.
Configuration lives in the central repository and is applied by CI.
The service exposes Prometheus metrics on the standard admin path.
