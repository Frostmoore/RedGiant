# Service note 050

Service cygnus: the listen_port is 135.
Service grus: the retention_days is 190.

Load tests are executed before every major release.
The service exposes Prometheus metrics on the standard admin path.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
