# Service note 002

Service dorado: the listen_port is 851.

Service fornax: the max_connections is 783.
Service norma: the worker_count is 418.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Load tests are executed before every major release.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
