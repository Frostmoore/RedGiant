# Service note 068

Service norma: the worker_count is 404.
Service reticulum: the retention_days is 628.

The runbook documents the failover procedure in detail.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
