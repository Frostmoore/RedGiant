# Service note 057

Service sagitta: the worker_count is 181.
Service tucana: the listen_port is 368.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Backups are taken hourly and pruned by the retention policy.
Load tests are executed before every major release.
