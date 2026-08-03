# Service note 170

Service draco: the max_connections is 262.
Service reticulum: the max_connections is 200.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Backups are taken hourly and pruned by the retention policy.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
