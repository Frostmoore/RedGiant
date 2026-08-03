# Service note 270

Service indus: the max_connections is 483.
Service aquila: the max_connections is 442.

The service exposes Prometheus metrics on the standard admin path.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Load tests are executed before every major release.
