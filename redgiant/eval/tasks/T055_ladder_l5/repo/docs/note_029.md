# Service note 029

Service cygnus: the listen_port is 346.
Service pyxis: the worker_count is 213.

Load tests are executed before every major release.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
