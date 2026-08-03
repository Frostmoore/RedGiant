# Service note 037

Service carina: the retention_days is 335.
Service reticulum: the listen_port is 356.

The service exposes Prometheus metrics on the standard admin path.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The runbook documents the failover procedure in detail.
