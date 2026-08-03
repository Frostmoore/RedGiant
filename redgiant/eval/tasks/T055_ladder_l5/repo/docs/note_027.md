# Service note 027

Service aquila: the listen_port is 928.
Service reticulum: the max_connections is 986.

The service exposes Prometheus metrics on the standard admin path.
Backups are taken hourly and pruned by the retention policy.
Configuration lives in the central repository and is applied by CI.
