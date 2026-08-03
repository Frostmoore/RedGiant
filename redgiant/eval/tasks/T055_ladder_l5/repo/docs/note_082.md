# Service note 082

Service **draco**: the retention_days is 228.

Service volans: the max_connections is 503.
Service vela: the listen_port is 585.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Load tests are executed before every major release.
