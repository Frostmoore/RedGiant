# Service note 040

Service **orion**: the cache_size_mb is 759.

Service atlas: the listen_port is 101.
Service aquila: the listen_port is 303.

The service exposes Prometheus metrics on the standard admin path.
Backups are taken hourly and pruned by the retention policy.
Configuration lives in the central repository and is applied by CI.
