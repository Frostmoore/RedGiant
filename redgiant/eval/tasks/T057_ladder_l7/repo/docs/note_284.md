# Service note 284

Service sagitta: the listen_port is 293.
Service aquila: the max_connections is 384.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Backups are taken hourly and pruned by the retention policy.
The service exposes Prometheus metrics on the standard admin path.
