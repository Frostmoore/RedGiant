# Service note 006

Service lyra: the retention_days is 721.
Service vela: the listen_port is 411.

Backups are taken hourly and pruned by the retention policy.
Configuration lives in the central repository and is applied by CI.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
