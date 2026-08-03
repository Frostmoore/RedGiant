# Service note 174

Service phoenix: the max_connections is 754.
Service indus: the max_connections is 187.

Configuration lives in the central repository and is applied by CI.
Backups are taken hourly and pruned by the retention policy.
Load tests are executed before every major release.
