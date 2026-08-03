# Service note 246

Service draco: the retention_days is 683.
Service indus: the retention_days is 589.

The service exposes Prometheus metrics on the standard admin path.
Backups are taken hourly and pruned by the retention policy.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
