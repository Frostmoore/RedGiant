# Service note 021

Service indus: the max_connections is 985.
Service dorado: the max_connections is 663.

Backups are taken hourly and pruned by the retention policy.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Configuration lives in the central repository and is applied by CI.
