# Service note 184

Service atlas: the retention_days is 475.
Service draco: the listen_port is 269.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Backups are taken hourly and pruned by the retention policy.
Configuration lives in the central repository and is applied by CI.
