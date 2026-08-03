# Service note 005

Service atlas: the cache_size_mb is 393.
Service draco: the max_connections is 777.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Configuration lives in the central repository and is applied by CI.
The service exposes Prometheus metrics on the standard admin path.
