# App catalog

Everything Home Server installs and how it sets it up, published as signed releases that the
installer and installed servers download. See [Releasing the app catalog](../README.md#releasing-the-app-catalog).

| File | What it is |
|---|---|
| `catalog.json` | Version number, the installer's app checklist, which apps need which, and each app's download, disk and memory size |
| `compose.yaml` | Every app as a Docker Compose service with its own profile, each image pinned to a tag and digest |
| `apps.py` | Reads `catalog.json`: dependency rules, the installer's checklist, and what the Cockpit page shows and plans |
| `apps.sh` | Adds and removes apps on an installed server (the Cockpit page runs it through `catalog.sh apps`) |
| `configure-apps.sh`, `setup.py` | Download and configure the picked apps and connect them to each other; also drop the links to removed apps |
| `update.sh` | What a server runs after taking a new catalog release: move the apps to the pinned versions, rewrite the dashboard |
| `release.sh` | Signs and publishes a release (not part of it) |

To move an app to a new version, change its `image:` line (tag and `@sha256:` digest), raise
`version` in `catalog.json`, test it in the VM, and release.
