# homeserver-usb

A USB stick that turns any spare computer into a home server, for people who have never used Linux.

You flash one file onto a USB stick, boot the computer from it, and answer a few questions in a
point-and-click installer: language, which disk to use, which apps you want, your name and a
password. It installs Debian with Docker, sets up the apps you picked, connects them to each other,
and leaves the computer showing a dashboard with everything on it. No terminal at any point.

The stick holds Debian and the installer; the apps are downloaded during the install, so connect
the computer to your router with a cable. Without internet the system still installs, and the apps
download and set themselves up the first time it starts with a connection.

## What you get

Every app has its own checkbox in the installer, and all of them are ticked by default. Apps that
another app needs are added automatically (Seerr adds Jellyfin; Sonarr, Radarr and Chaptarr add
qBittorrent if no downloader is ticked). Homepage is always installed.

| App | What it's for |
|---|---|
| [Homepage](https://gethomepage.dev) | The dashboard, shown full screen on the server and on `http://homeserver.local`. Apps appear on it through Docker labels, with live status, and open in a new tab |
| [File Browser](https://filebrowser.org) | Browse, upload and download files from a browser |
| Shared folder | A Samba share (`\\homeserver\Media`) that shows up on Windows and Mac |
| [Jellyfin](https://jellyfin.org) | Movies and shows, with the libraries already created |
| [Seerr](https://github.com/seerr-team/seerr) | Request a movie or show; signed in through Jellyfin and linked to Sonarr and Radarr |
| [Audiobookshelf](https://www.audiobookshelf.org) | Audiobooks, ebooks and podcasts, with the libraries already created |
| Sonarr, Radarr, [Chaptarr](https://hub.docker.com/r/chaptarr/chaptarr) | TV, movies, and books/audiobooks, each linked to every installed downloader with its own category |
| Prowlarr | Download sources, shared with Sonarr, Radarr and Chaptarr |
| Bazarr | Subtitles, linked to Sonarr and Radarr |
| [Recyclarr](https://recyclarr.dev) | Keeps Sonarr and Radarr on the TRaSH Guides profiles |
| qBittorrent | Torrent downloader |
| [SABnzbd](https://sabnzbd.org) | Usenet downloader; you add your own Usenet provider |

Always installed: [Cockpit](https://cockpit-project.org) for server settings (port 9090: updates,
disks, restart, shut down) and automatic security updates.

Every app is configured during the install, and all of them use the **name and password typed in the
installer**. The only things left to do are adding your indexers in Prowlarr and, for Usenet, your
provider in SABnzbd.

The download setup follows the [TRaSH Guides](https://trash-guides.info):

- One `/data` folder shared by every app, so finished downloads are hardlinked into the library
  instead of copied: `/srv/data/torrents/...` for qBittorrent, `/srv/data/usenet/...` for SABnzbd and
  `/srv/data/media/...` for the libraries.
- qBittorrent (automatic torrent management) and SABnzbd use one category per media type.
- Sonarr and Radarr have hardlinks, subtitle import and "do not prefer" propers. Recyclarr syncs the
  TRaSH WEB-1080p (Sonarr) and HD Bluray + WEB (Radarr) profiles, custom formats and the Jellyfin
  naming schemes daily, and Seerr requests use those profiles.

### Disks

The disk you pick is split into EFI, `/boot`, swap, `/` (30%, 20–50 GB), `/home` (10%, 5–10 GB) and
`/srv` (the rest) for app settings and media. There's also a manual option.

Other drives in the computer can be ticked on the next page. They're **erased** and pooled with the
main drive's media folder using [mergerfs](https://github.com/trapexit/mergerfs): every drive keeps
its own filesystem, so a dead drive only loses the files that were on it, and any drive can be read
on another computer. New folders go to the drive with the most free space, and their contents stay
together. When a download and its library folder end up on different drives, the app copies the
file instead of hardlinking it.

## Install

The [step-by-step guide with screenshots](docs/install-guide.md) walks through all of it. In short:

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
- `server/` is copied onto the installed system. `setup-drives.sh` erases and pools any extra drives.
  At the end of the install, `install-apps.sh` starts a temporary Docker daemon that writes to the
  new disk and downloads only the apps you picked.
  `configure-apps.sh` then has `setup.py` write each app's config (API keys, paths, logins), starts
  everything with `compose.yaml`, and connects the apps through their APIs. If that fails, the
  installed system retries it on its first start.
- The screen shows the dashboard in Firefox running under [cage](https://github.com/cage-kiosk/cage).

## Build it yourself

You need Docker and about 15 GB of free disk:

```bash
./build.sh             # writes out/homeserver-usb.iso
test/vm.sh --reset     # boots it in a VM as a USB stick, with two empty disks (64 GB, 500 GB)
test/vm.sh --window    # same, in a window you can click through
test/vm.sh --disk      # boots the installed VM
```

## Security notes

This is meant for a home network. The dashboard has no login, and everything uses plain HTTP.
Don't forward these ports to the internet.

## Known issues

- Firefox on the server's screen shows "This connection is not secure" under login forms. Every app
  is plain HTTP inside the home network, so it's expected; click anywhere to dismiss it.
- Right after a reboot some dashboard tiles can show "API Error" while their app is still
  starting. The dashboard reloads itself until they're up.

## License

MIT
