# Service note 066

Service **vela**: the retention_days is 151.

Service tucana: the max_connections is 586.
Service indus: the retention_days is 560.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
The service exposes Prometheus metrics on the standard admin path.
Backups are taken hourly and pruned by the retention policy.
