# Service note 012

Service carina: the retention_days is 176.
Service draco: the max_connections is 384.

Configuration lives in the central repository and is applied by CI.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
The service exposes Prometheus metrics on the standard admin path.
