import os
import secrets
import shutil

import libcalamares
from libcalamares.utils import debug, warning

# Checklist entry (a "package" in netinstall.conf) -> app id. Every entry here, and every extra
# drive (/dev/... from netinstall-drives.conf), is removed from the package list before the
# packages step, so apt never sees them.
APPS = {
    "Homepage": "homepage",
    "File Browser": "filebrowser",
    "Jellyfin": "jellyfin",
    "Seerr": "seerr",
    "Audiobookshelf": "audiobookshelf",
    "Sonarr": "sonarr",
    "Radarr": "radarr",
    "Chaptarr": "chaptarr",
    "Prowlarr": "prowlarr",
    "Bazarr": "bazarr",
    "Recyclarr": "recyclarr",
    "qBittorrent": "qbittorrent",
    "Flood": "flood",
    "Shared folder": "files",
}
# Listed for information only; installed with the system either way.
FIXED = {"Cockpit", "Automatic security updates"}

# app -> apps it can't work without
NEEDS = {
    "seerr": ["jellyfin"],
    "sonarr": ["qbittorrent"],
    "radarr": ["qbittorrent"],
    "chaptarr": ["qbittorrent"],
    "flood": ["qbittorrent"],
}
# app -> it needs at least one of these; if none was picked, all of them are added
NEEDS_ONE_OF = {
    "seerr": ["sonarr", "radarr"],
    "bazarr": ["sonarr", "radarr"],
    "recyclarr": ["sonarr", "radarr"],
    "prowlarr": ["sonarr", "radarr", "chaptarr"],
}


def pretty_name():
    return "Saving your choices"


def package_name(entry):
    if isinstance(entry, dict):
        return entry.get("package") or entry.get("name") or ""
    return str(entry)


def take_checklist(gs):
    """Returns the ticked checklist entries and removes them from the package list."""
    ticked = set()
    operations = []
    for op in gs.value("packageOperations") or []:
        kept = {}
        for action, entries in op.items():
            if not isinstance(entries, list):
                kept[action] = entries
                continue
            rest = []
            for entry in entries:
                name = package_name(entry)
                if name in APPS or name in FIXED or name.startswith("/dev/"):
                    ticked.add(name)
                else:
                    rest.append(entry)
            if rest:
                kept[action] = rest
        if any(isinstance(v, list) for v in kept.values()):
            operations.append(kept)
    gs.insert("packageOperations", operations)
    return ticked


def resolve(apps):
    apps = set(apps)
    changed = True
    while changed:
        before = set(apps)
        for app in list(apps):
            apps.update(NEEDS.get(app, []))
            options = NEEDS_ONE_OF.get(app)
            if options and not apps.intersection(options):
                apps.update(options)
        changed = apps != before
    return sorted(apps)


def write(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    os.chmod(path, mode)


def run():
    gs = libcalamares.globalstorage
    root = gs.value("rootMountPoint")
    user = gs.value("username")
    ticked = take_checklist(gs)
    picked = {APPS[name] for name in ticked if name in APPS}
    drives = sorted(name for name in ticked if name.startswith("/dev/"))
    apps = resolve(picked)
    etc = os.path.join(root, "etc/homeserver")
    debug("homeserver: picked={} installing={} drives={} user={}".format(sorted(picked), apps, drives, user))
    write(os.path.join(etc, "drives"), "".join(d + "\n" for d in drives))

    obscured = gs.value("password")
    if obscured:
        password = libcalamares.utils.obscure(obscured)
    else:
        warning("homeserver: no password in global storage; generating one for the apps")
        password = secrets.token_urlsafe(9)
        write(os.path.join(etc, "password-generated"), "")
    write(os.path.join(etc, "password"), password, 0o600)

    profiles = [a for a in apps if a != "files"]
    write(os.path.join(etc, "homeserver.env"),
          'OWNER="{}"\nAPPS="{}"\nCOMPOSE_PROFILES="{}"\n'.format(user, " ".join(apps), ",".join(profiles)))

    if "files" in apps:
        with open(os.path.join(root, "etc/samba/smb.conf"), "a") as f:
            f.write("\n[Media]\n   path = /srv/data/media\n   valid users = {}\n   read only = no\n".format(user))

    shutil.rmtree(os.path.join(root, "etc/calamares"), ignore_errors=True)
    return None
