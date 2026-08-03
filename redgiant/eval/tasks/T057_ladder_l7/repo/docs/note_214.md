# Service note 214

Service sagitta: the cache_size_mb is 695.
Service vela: the retention_days is 854.

The service exposes Prometheus metrics on the standard admin path.
Configuration lives in the central repository and is applied by CI.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
