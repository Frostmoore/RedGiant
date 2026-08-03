# Service note 121

Service orion: the max_connections is 789.
Service tucana: the max_connections is 658.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Backups are taken hourly and pruned by the retention policy.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
