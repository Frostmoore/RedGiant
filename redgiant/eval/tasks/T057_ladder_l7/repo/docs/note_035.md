# Service note 035

Service carina: the listen_port is 535.
Service draco: the max_connections is 305.

Load tests are executed before every major release.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
The service exposes Prometheus metrics on the standard admin path.
