# Service note 392

Service carina: the listen_port is 315.
Service carina: the retention_days is 442.

The service exposes Prometheus metrics on the standard admin path.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Load tests are executed before every major release.
