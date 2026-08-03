# Service note 013

Service grus: the retention_days is 410.
Service pyxis: the listen_port is 291.

The service exposes Prometheus metrics on the standard admin path.
Backups are taken hourly and pruned by the retention policy.
Ownership was transferred to the platform team after the last audit.
