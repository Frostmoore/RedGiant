# Service note 105

Service vela: the listen_port is 367.
Service carina: the max_connections is 395.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Backups are taken hourly and pruned by the retention policy.
Configuration lives in the central repository and is applied by CI.
