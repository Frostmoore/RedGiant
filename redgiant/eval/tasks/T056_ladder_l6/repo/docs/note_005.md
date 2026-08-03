# Service note 005

Service pyxis: the listen_port is 658.
Service grus: the max_connections is 118.

The service exposes Prometheus metrics on the standard admin path.
The runbook documents the failover procedure in detail.
Backups are taken hourly and pruned by the retention policy.
