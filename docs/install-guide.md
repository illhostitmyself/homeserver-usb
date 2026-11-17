# Installing your home server, step by step

This guide walks through the whole install with pictures. It takes about half an hour, most of it
waiting. You need:

- the computer that will become the server, with a keyboard, mouse and screen plugged in
- a network cable from that computer to your internet router, or your Wi-Fi name and password
  (a cable is faster and more reliable for streaming)
- a USB stick of 8 GB or more (everything on it is erased)
- another computer to prepare the USB stick

> **Everything on the computer you install on is erased.** Copy off anything you want to keep first.

## 1. Put the installer on the USB stick

1. Download `homeserver-usb.iso` from the [Releases page](https://github.com/illhostitmyself/homeserver-usb/releases).
2. Download and open [balenaEtcher](https://etcher.balena.io) (the simplest) or [Rufus](https://rufus.ie).
3. Pick the file you downloaded, pick your USB stick, and press **Flash** (Etcher) or **Start** (Rufus).
   If Rufus asks how to write the image, choose **DD Image mode**.
4. When it's done, take the USB stick out.

## 2. Start the computer from the USB stick

Plug the USB stick into the server computer and turn it on. Straight away, tap the boot menu key
over and over. On most computers it's **F12**, **F11**, **F10** or **Esc**; the screen often says
which one for a second. Pick the USB stick from the list.

A black menu appears. You don't need to touch anything: it starts on its own after 5 seconds.

![Boot menu](screenshots/01-boot-menu.png)

**No network cable?** If the computer has Wi-Fi, a screen asks you to connect first. Press
**Enter**, use the arrow keys to pick your network, press **Enter**, and type the Wi-Fi password.
It moves on to the installer by itself once it's connected. The server keeps using that Wi-Fi
after the install.

![Wi-Fi](screenshots/02a-wifi.png)

Once it's online, the installer downloads the newest list of apps and their settings from the Home
Server repository. Without internet it still installs, but only offers the dashboard and Cockpit.
You can add the other apps later from the **Apps** page, once the server is online (see
[Adding and removing apps](#adding-and-removing-apps)).

## 3. Answer the installer's questions

The installer shows a list of steps on the left. Click **Next** at the bottom right to go forward,
or **Back** to change something.

**Welcome.** Pick your language at the bottom, then **Next**.

![Welcome](screenshots/02-welcome.png)

**Location.** Click your country on the map, or pick it from the two lists. This sets the clock.

![Location](screenshots/03-location.png)

**Keyboard.** Usually already right. Type in the box at the bottom to test it.

![Keyboard](screenshots/04-keyboard.png)

**Partitions.** Pick the drive to install on from the list at the top, and keep **Erase disk**
selected. The bar at the bottom shows how the drive will be split. On your computer the list shows
your own drive names instead of "QEMU".

![Partitions](screenshots/05-partitions.png)

**Drives.** Only if the computer has more than one drive. Tick the extra drives you want to use for
movies, shows and books: they are **erased** and joined with the main drive into one big storage.
If one of them ever breaks, only the files on that drive are lost. Leave everything unticked if you
only have one drive. Ticking the drive you install on does nothing; it's skipped.

![Drives](screenshots/06-drives.png)

**Apps.** Everything is ticked. Untick anything you don't want. If you untick something another
app needs, it's added back for you.

![Apps](screenshots/07-apps.png)

**Users.** Type your name. The login name and the computer name fill in by themselves. Pick a
password and type it twice. **This one name and password open every app on the server**, so write
it down somewhere safe. Very common passwords aren't accepted.

![Users](screenshots/08-users.png)

**Review.** What's about to happen: which drives are erased, which apps are installed, and how much
internet, disk space and memory they need.

![Review](screenshots/09-review.png)

**Summary.** The technical version of the same thing. Click **Install**, then **Install Now** to
start.

![Summary](screenshots/10-summary.png)

![Install Now](screenshots/11-confirm.png)

## 4. Wait

The install takes 15 to 30 minutes. Most of that is downloading your apps, so stay
connected. You don't need to do anything.

![Installing](screenshots/12-installing.png)

When it says **All done**, click **Done**. The computer turns itself off. **Now pull out the USB
stick**, then press the power button.

![All done](screenshots/13-done.png)

## 5. Your dashboard

The first start shows this page for a minute or two while the apps start up:

![Getting ready](screenshots/14-getting-ready.png)

Then the dashboard appears. It has a tile for every app, and it's what this computer's screen shows
from now on. Click a tile to open that app in a new tab.

![Dashboard](screenshots/15-dashboard.png)

From any other computer, phone or tablet at home, open **http://homeserver.local** in a web browser
to see the same dashboard. If that doesn't work, use the address shown on the server's screen when
you press Ctrl+Alt+F2 (something like `http://192.168.1.20`), then Ctrl+Alt+F1 to go back.

## 6. Log in to the apps

Every app asks for a login the first time. Use the name and password from the Users step. Your
browser can remember them.

| | |
|---|---|
| ![Jellyfin](screenshots/app-jellyfin.png) | ![Sonarr](screenshots/app-sonarr.png) |
| ![Audiobookshelf](screenshots/app-audiobookshelf.png) | ![Chaptarr](screenshots/app-chaptarr.png) |
| ![Bazarr](screenshots/app-bazarr.png) | ![qBittorrent](screenshots/app-qbittorrent.png) |
| ![SABnzbd](screenshots/app-sabnzbd.png) | ![File Browser](screenshots/app-filebrowser.png) |
| ![Server settings](screenshots/app-cockpit.png) | |

## 7. The two things left to do

Everything else is already set up and connected. These two need your own accounts, so they're up
to you:

**Add your download sources in Prowlarr** ("Download sources" on the dashboard). Click **Add New
Indexer** and pick the ones you use. Sonarr, Radarr and Chaptarr get them automatically.

![Prowlarr](screenshots/step-prowlarr.png)

**If you use Usenet, add your provider in SABnzbd** ("Usenet downloads" on the dashboard). The
first time, it opens a short wizard that asks for your provider's server name, username and
password. Skip this if you don't have a Usenet provider.

![SABnzbd](screenshots/step-sabnzbd.png)

## Adding and removing apps

Click **Apps** in the Server row at the bottom of the dashboard and log in with your name and
password.

![Apps tile](screenshots/16-apps-tile.png)

Under **Your apps**, tick the apps you want and untick the ones you don't. The page shows what will
be added and removed, and how much it downloads. Apps another app needs are ticked for you and can't
be unticked while that app is there. Type your password and click **Apply changes**. New apps get
your name and password and appear on the dashboard when it's done.

![Add or remove apps](screenshots/21-add-remove-apps.png)

Removing an app keeps its settings, so adding it back later picks up where it left off. Your files,
downloads and media are never removed.

## Updating later

There are two kinds of updates. Neither erases anything.

### Your apps: from the dashboard

The apps' settings and versions come from the Home Server app catalog. When a new catalog is out,
click **Apps** in the Server row at the bottom of the dashboard and log in. The page says whether an
update is available; click **Update the apps**.

![App updates](screenshots/17-app-updates.png)

It downloads the new catalog, checks that it really comes from Home Server, and moves your apps to
the new versions. If anything goes wrong, it puts the previous versions back on its own.

![App updates done](screenshots/18-app-updates-done.png)

### The whole server: from a new USB stick

New versions of the USB stick also update the server itself (for example, Wi-Fi support). Flash the
new version to the USB stick and start the server from it, as in step 2. Instead of the installer
you see **Home Server is already on this computer**, with your disk and apps. Click **Next**.

![Already installed](screenshots/19-update-found.png)

When it says **Your server is up to date**, take out the USB stick and click **Done**. Click
**Cancel** on the first page only if you want to erase everything and install from scratch.

![Up to date](screenshots/20-update-done.png)

## Where things are

| On the dashboard | What it's for |
|---|---|
| Movies & TV (Jellyfin) | Watch your movies and shows, here or on your TV and phone (get the Jellyfin app) |
| Request a movie or show (Seerr) | Ask for something by name; it's found and downloaded for you |
| Audiobooks & podcasts | Listen here or with the Audiobookshelf phone app |
| Files | Upload, download and organize files in the browser |
| Server settings (Cockpit) | Updates, disks, restart and shut down |
| Apps | Add and remove apps, and install new versions when a new app catalog is out |

On Windows, the shared folder is at `\\homeserver\Media` in File Explorer.
