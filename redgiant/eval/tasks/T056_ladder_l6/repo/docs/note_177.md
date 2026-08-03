# Service note 177

Service sagitta: the worker_count is 430.
Service eridanus: the listen_port is 960.

Configuration lives in the central repository and is applied by CI.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
The service exposes Prometheus metrics on the standard admin path.
