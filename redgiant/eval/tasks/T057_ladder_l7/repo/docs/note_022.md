# Service note 022

Service aquila: the max_connections is 413.
Service grus: the worker_count is 984.

The service exposes Prometheus metrics on the standard admin path.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Ownership was transferred to the platform team after the last audit.
