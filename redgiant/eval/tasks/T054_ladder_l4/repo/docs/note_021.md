# Service note 021

Service mensa: the listen_port is 857.
Service draco: the max_connections is 467.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
The service exposes Prometheus metrics on the standard admin path.
Backups are taken hourly and pruned by the retention policy.
