# homeserver-usb

A USB stick that turns any spare computer into a home server, for people who have never used Linux.

You flash one file onto a USB stick, boot the computer from it, and answer a few questions in a
point-and-click installer: language, which disk to use, which apps you want, your name and a
password. It installs Debian with Docker, sets up the apps you picked, connects them to each other,
and leaves the computer showing a dashboard with everything on it. No terminal at any point.

Everything is on the stick, so it installs without internet. Apps that download things obviously
need internet once they're running.

## What you get

Always installed:

- **Dashboard** ([Homepage](https://gethomepage.dev)) on `http://homeserver.local`, also shown full screen on
  the server's own monitor. Apps appear on it automatically through Docker labels, with live status.
- **Files** ([File Browser](https://filebrowser.org)) to browse, upload and download from the browser
- **Server settings** ([Cockpit](https://cockpit-project.org)) on port 9090: updates, disks, restart, shut down
- **Security updates** installed automatically

Optional, all ticked by default:

| In the installer | What you get |
|---|---|
| Movies & TV | [Jellyfin](https://jellyfin.org) with Movies and Shows libraries already created |
| Shared folder | A Samba share (`\\homeserver\Media`) that shows up on Windows and Mac |
| Automatic downloads | Sonarr, Radarr, Prowlarr, qBittorrent and [Recyclarr](https://recyclarr.dev), connected to each other |
| Request page | [Seerr](https://github.com/seerr-team/seerr), signed in through Jellyfin and connected to Sonarr and Radarr. Picking it adds Movies & TV and Automatic downloads |

Every app is configured during the install, and all of them use the **name and password typed in the
installer**. The only thing left to do is add your indexers in Prowlarr.

The download setup follows the [TRaSH Guides](https://trash-guides.info):

- One `/data` folder shared by every app, so finished downloads are hardlinked into the library
  instantly, with no copies: `/srv/data/torrents/{movies,tv}` for qBittorrent and
  `/srv/data/media/{movies,tv}` for Jellyfin.
- qBittorrent uses automatic torrent management with `movies` and `tv` categories.
- Sonarr and Radarr have hardlinks, subtitle import and "do not prefer" propers. Recyclarr syncs the
  TRaSH WEB-1080p (Sonarr) and HD Bluray + WEB (Radarr) profiles, custom formats and the Jellyfin
  naming schemes once a day. This part needs internet; on an offline install it starts working
  the first day the server is online.
- Seerr requests use those profiles.

The disk you pick is split into EFI, `/boot`, swap, `/` (30%, 20–50 GB), `/home` (10%, 5–10 GB) and
`/srv` (the rest) for media and app data.

## Install

1. Download `homeserver-usb.iso` from [Releases](../../releases).
2. Flash it to a USB stick (8 GB or bigger) with [balenaEtcher](https://etcher.balena.io) or
   [Rufus](https://rufus.ie). If Rufus asks, choose **DD Image mode**.
3. Plug the stick into the computer that will become the server, connect it to your router with a
   network cable, and boot from the stick (usually F12, F11 or Esc at power-on).
4. Follow the installer. **The disk you pick is erased.**
5. When it's done the computer turns off. Pull out the stick and turn it back on.
6. The dashboard opens on the server's screen. From any other device at home, open
   `http://homeserver.local`.
7. In Prowlarr ("Download sources" on the dashboard), add your indexers.

Needs a 64-bit PC with 4 GB of RAM and a 64 GB disk.

## How it works

- `live/` is a [live-build](https://live-team.pages.debian.net/live-manual/) config for a Debian 13
  live system that boots straight into [Calamares](https://calamares.io), full screen, with no desktop.
- `installer/` holds the Calamares settings, branding, and a small Python step
  (`usr/lib/calamares/modules/homeserver`) that saves your choices.
- `server/` is copied onto the installed system. At the end of the install, `install-apps.sh` starts
  a temporary Docker daemon that writes to the new disk and loads only the images you picked.
  `configure-apps.sh` then has `setup.py` write each app's config (API keys, paths, logins), starts
  everything with `compose.yaml`, and connects the apps through their APIs. If that fails, the
  installed system retries it on its first start.
- The screen shows the dashboard in Firefox running under [cage](https://github.com/cage-kiosk/cage).

## Build it yourself

You need Docker and about 20 GB of free disk:

```bash
./build.sh             # writes out/homeserver-usb.iso
test/vm.sh --reset     # boots it in a VM as a USB stick, with two empty disks
test/vm.sh --disk      # boots the installed VM
```

Container images are cached in `build/images`. Use `REFRESH_IMAGES=1 ./build.sh` to fetch new versions.

## Security notes

This is meant for a home network. The dashboard has no login, and everything uses plain HTTP.
Don't forward these ports to the internet.

## License

MIT
