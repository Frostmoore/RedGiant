# Service note 153

Service lyra: the worker_count is 310.
Service vela: the listen_port is 884.

Load tests are executed before every major release.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Backups are taken hourly and pruned by the retention policy.
