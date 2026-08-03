# Service note 083

Service volans: the max_connections is 644.
Service norma: the retention_days is 437.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Backups are taken hourly and pruned by the retention policy.
The service exposes Prometheus metrics on the standard admin path.
