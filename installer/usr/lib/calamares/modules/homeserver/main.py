import os
import secrets
import shutil

import libcalamares
from libcalamares.utils import debug, warning

# App id (from packagechooser-apps.conf) -> bundled images it needs.
APP_IMAGES = {
    "jellyfin": ["jellyfin"],
    "files": [],
    "downloads": ["sonarr", "radarr", "prowlarr", "qbittorrent", "recyclarr"],
    "requests": ["seerr"],
}
ALWAYS_IMAGES = ["homepage", "filebrowser"]


def pretty_name():
    return "Saving your choices"


MARKER = "homeserver-app-"


def package_name(entry):
    return entry.get("package", "") if isinstance(entry, dict) else str(entry)


def chosen_apps(gs):
    """Reads the ticked apps from netinstall's package list and removes the markers from it."""
    apps = set()
    operations = []
    for op in gs.value("packageOperations") or []:
        kept = {}
        for action, entries in op.items():
            if not isinstance(entries, list):
                kept[action] = entries
                continue
            for entry in entries:
                if package_name(entry).startswith(MARKER):
                    apps.add(package_name(entry)[len(MARKER):])
            rest = [e for e in entries if not package_name(e).startswith(MARKER)]
            if rest:
                kept[action] = rest
        if any(isinstance(v, list) for v in kept.values()):
            operations.append(kept)
    gs.insert("packageOperations", operations)

    if "requests" in apps:
        apps |= {"jellyfin", "downloads"}
    return sorted(a for a in apps if a in APP_IMAGES)


def write(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    os.chmod(path, mode)


def run():
    gs = libcalamares.globalstorage
    root = gs.value("rootMountPoint")
    user = gs.value("username")
    apps = chosen_apps(gs)
    etc = os.path.join(root, "etc/homeserver")
    debug("homeserver: apps={} user={}".format(apps, user))

    obscured = gs.value("password")
    if obscured:
        password = libcalamares.utils.obscure(obscured)
    else:
        warning("homeserver: no password in global storage; generating one for the apps")
        password = secrets.token_urlsafe(9)
        write(os.path.join(etc, "password-generated"), "")
    write(os.path.join(etc, "password"), password, 0o600)

    images = ALWAYS_IMAGES + [i for a in apps for i in APP_IMAGES[a]]
    profiles = [a for a in apps if a != "files"]
    write(os.path.join(etc, "homeserver.env"),
          'OWNER="{}"\nAPPS="{}"\nIMAGES="{}"\nCOMPOSE_PROFILES="{}"\n'.format(
              user, " ".join(apps), " ".join(images), ",".join(profiles)))

    if "files" in apps:
        with open(os.path.join(root, "etc/samba/smb.conf"), "a") as f:
            f.write("\n[Media]\n   path = /srv/data/media\n   valid users = {}\n   read only = no\n".format(user))

    shutil.rmtree(os.path.join(root, "etc/calamares"), ignore_errors=True)
    return None
