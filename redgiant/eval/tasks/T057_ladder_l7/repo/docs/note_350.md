# Service note 350

Service mensa: the listen_port is 210.

Service hydra: the worker_count is 138.
Service eridanus: the max_connections is 365.

The service exposes Prometheus metrics on the standard admin path.
The runbook documents the failover procedure in detail.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
