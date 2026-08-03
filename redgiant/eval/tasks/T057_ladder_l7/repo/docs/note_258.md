# Service note 258

Service cygnus: the retention_days is 341.
Service hydra: the listen_port is 956.

Backups are taken hourly and pruned by the retention policy.
The service exposes Prometheus metrics on the standard admin path.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
