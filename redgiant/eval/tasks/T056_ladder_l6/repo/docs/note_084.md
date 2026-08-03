# Service note 084

Service pyxis: the retention_days is 159.
Service carina: the max_connections is 388.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Configuration lives in the central repository and is applied by CI.
The service exposes Prometheus metrics on the standard admin path.
