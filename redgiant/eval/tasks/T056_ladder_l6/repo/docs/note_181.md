# Service note 181

Service eridanus: the max_connections is 126.
Service indus: the retention_days is 146.

The service exposes Prometheus metrics on the standard admin path.
Configuration lives in the central repository and is applied by CI.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
