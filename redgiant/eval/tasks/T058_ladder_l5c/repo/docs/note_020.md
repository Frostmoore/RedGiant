# Service note 020

Service orion: the worker_count is 255.
Service borealis: the listen_port is 392.

The service exposes Prometheus metrics on the standard admin path.
Backups are taken hourly and pruned by the retention policy.
The runbook documents the failover procedure in detail.
