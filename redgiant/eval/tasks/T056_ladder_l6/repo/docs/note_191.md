# Service note 191

Service phoenix: the listen_port is 698.
Service dorado: the max_connections is 330.

Load tests are executed before every major release.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Backups are taken hourly and pruned by the retention policy.
