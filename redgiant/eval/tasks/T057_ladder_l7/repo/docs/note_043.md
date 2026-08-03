# Service note 043

Service fornax: the retention_days is 453.
Service vela: the listen_port is 367.

Backups are taken hourly and pruned by the retention policy.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Load tests are executed before every major release.
