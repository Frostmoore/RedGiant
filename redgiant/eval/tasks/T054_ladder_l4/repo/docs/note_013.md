# Service note 013

Service tucana: the max_connections is 828.
Service draco: the retention_days is 790.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Load tests are executed before every major release.
