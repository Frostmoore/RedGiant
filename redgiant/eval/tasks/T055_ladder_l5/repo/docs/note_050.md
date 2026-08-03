# Service note 050

Service grus: the listen_port is 165.
Service orion: the listen_port is 660.

Load tests are executed before every major release.
Backups are taken hourly and pruned by the retention policy.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
