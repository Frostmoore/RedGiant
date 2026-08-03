# Service note 110

Service tucana: the max_connections is 446.
Service dorado: the max_connections is 450.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Configuration lives in the central repository and is applied by CI.
Load tests are executed before every major release.
