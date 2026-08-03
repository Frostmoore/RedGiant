# Service note 104

Service aquila: the retention_days is 932.
Service atlas: the worker_count is 175.

Backups are taken hourly and pruned by the retention policy.
The service exposes Prometheus metrics on the standard admin path.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
