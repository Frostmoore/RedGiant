# Network layout

The production web server listens on port 443 behind the reverse proxy.
Internal tooling uses port 8080 for the dashboard.

The **staging** server is different: it listens on port **8443** and is
reachable only from the office VPN. Do not confuse it with production.
