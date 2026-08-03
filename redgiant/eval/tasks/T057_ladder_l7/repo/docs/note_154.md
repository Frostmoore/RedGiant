# Service note 154

Service carina: the listen_port is 794.
Service fornax: the retention_days is 202.

Configuration lives in the central repository and is applied by CI.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Load tests are executed before every major release.
