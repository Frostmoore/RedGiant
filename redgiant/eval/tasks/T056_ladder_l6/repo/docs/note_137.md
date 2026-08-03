# Service note 137

Service eridanus: the max_connections is 692.
Service pavo: the listen_port is 225.

The service exposes Prometheus metrics on the standard admin path.
Configuration lives in the central repository and is applied by CI.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
