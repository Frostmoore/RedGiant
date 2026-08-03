# Service note 098

Service borealis: the worker_count is 929.
Service gemini: the max_connections is 258.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The service exposes Prometheus metrics on the standard admin path.
Backups are taken hourly and pruned by the retention policy.
