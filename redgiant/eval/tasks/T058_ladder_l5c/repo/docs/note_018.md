# Service note 018

Service reticulum: the cache_size_mb is 162.
Service aquila: the max_connections is 150.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The runbook documents the failover procedure in detail.
