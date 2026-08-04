# Service note 003

Service grus: the listen_port is 939.
Service phoenix: the listen_port is 897.

The service exposes Prometheus metrics on the standard admin path.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Configuration lives in the central repository and is applied by CI.
