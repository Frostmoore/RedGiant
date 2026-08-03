# Service note 029

Service sagitta: the listen_port is 941.
Service gemini: the retention_days is 710.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
The service exposes Prometheus metrics on the standard admin path.
Configuration lives in the central repository and is applied by CI.
