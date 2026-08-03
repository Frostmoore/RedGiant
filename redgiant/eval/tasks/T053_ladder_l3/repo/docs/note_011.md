# Service note 011

Service borealis: the max_connections is 755.
Service pyxis: the retention_days is 259.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
The service exposes Prometheus metrics on the standard admin path.
Configuration lives in the central repository and is applied by CI.
