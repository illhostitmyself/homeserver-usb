import os
import shutil

import libcalamares
from libcalamares.utils import debug, target_env_call, warning

MEDIUM_IMAGES = "/run/live/medium/homeserver/images"

# App id (from packagechooser-apps.conf) -> bundled images it needs.
APP_IMAGES = {
    "jellyfin": ["jellyfin"],
    "files": [],
    "downloads": ["sonarr", "radarr", "prowlarr", "qbittorrent"],
    "requests": ["seerr"],
}
ALWAYS_IMAGES = ["homepage"]


def pretty_name():
    return "Setting up your apps"


def chosen_apps(gs):
    raw = gs.value("packagechooser_apps")
    if raw is None:
        for key in gs.keys():
            if key.startswith("packagechooser_"):
                raw = gs.value(key)
    if isinstance(raw, str):
        apps = {a.strip() for a in raw.split(",") if a.strip()}
    else:
        apps = set(raw or [])
    if "requests" in apps:
        apps |= {"jellyfin", "downloads"}
    return sorted(a for a in apps if a in APP_IMAGES)


def write(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    os.chmod(path, mode)


def copy_images(names, dest):
    os.makedirs(dest, exist_ok=True)
    files = [os.path.join(MEDIUM_IMAGES, n + ".tar.zst") for n in names]
    total = sum(os.path.getsize(f) for f in files) or 1
    done = 0
    for src in files:
        with open(src, "rb") as fin, open(os.path.join(dest, os.path.basename(src)), "wb") as fout:
            while chunk := fin.read(8 << 20):
                fout.write(chunk)
                done += len(chunk)
                libcalamares.job.setprogress(done / total)


def run():
    gs = libcalamares.globalstorage
    root = gs.value("rootMountPoint")
    user = gs.value("username")
    apps = chosen_apps(gs)
    debug("homeserver: apps={} user={}".format(apps, user))

    password = None
    obscured = gs.value("password")
    if obscured:
        password = libcalamares.utils.obscure(obscured)
    else:
        warning("homeserver: no password in global storage; apps will get a generated one")

    profiles = [a for a in apps if a != "files"]
    write(os.path.join(root, "etc/homeserver/homeserver.env"),
          "OWNER={}\nAPPS=\"{}\"\nCOMPOSE_PROFILES={}\n".format(user, " ".join(apps), ",".join(profiles)))
    if password:
        write(os.path.join(root, "etc/homeserver/owner-password"), password, 0o600)

    images = ALWAYS_IMAGES + [i for a in apps for i in APP_IMAGES[a]]
    copy_images(images, os.path.join(root, "var/lib/homeserver/images"))

    samba_units = ["smbd.service", "nmbd.service", "wsdd2.service"]
    if "files" in apps:
        with open(os.path.join(root, "etc/samba/smb.conf"), "a") as f:
            f.write("\n[Media]\n   path = /srv/media\n   valid users = {}\n   read only = no\n".format(user))
        target_env_call(["systemctl", "enable"] + samba_units)

    shutil.rmtree(os.path.join(root, "etc/calamares"), ignore_errors=True)
    return None
