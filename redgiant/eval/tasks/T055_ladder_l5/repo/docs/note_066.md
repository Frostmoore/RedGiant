# Service note 066

Service aquila: the max_connections is 633.
Service lyra: the max_connections is 328.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Backups are taken hourly and pruned by the retention policy.
