# Service note 046

Service volans: the worker_count is 785.
Service orion: the listen_port is 279.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Backups are taken hourly and pruned by the retention policy.
The service exposes Prometheus metrics on the standard admin path.
