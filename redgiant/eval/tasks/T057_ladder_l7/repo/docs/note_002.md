# Service note 002

Service draco: the retention_days is 579.
Service draco: the retention_days is 418.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Backups are taken hourly and pruned by the retention policy.
The service exposes Prometheus metrics on the standard admin path.
