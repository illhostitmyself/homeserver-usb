import os
import re
import secrets
import shutil
import sys

import libcalamares
from libcalamares.utils import debug, warning

# The app list and its rules come from the app catalog that installer-scale.sh fetched (or the
# minimal one on the stick). It's copied onto the new system, which installs and updates from it.
CATALOG = "/run/homeserver/catalog"
sys.path.insert(0, CATALOG)
import apps as catalog  # noqa: E402

# Extra drives are listed as "<model>, <size> (/dev/...)".
DRIVE = re.compile(r"\((/dev/[^)]+)\)$")


def pretty_name():
    return "Saving your choices"


def package_name(entry):
    if isinstance(entry, dict):
        return entry.get("package") or entry.get("name") or ""
    return str(entry)


def take_checklist(gs, names):
    """Returns the ticked checklist entries and removes them (and the extra drives) from the
    package list, so apt never sees them."""
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
                if name in names or DRIVE.search(name):
                    ticked.add(name)
                else:
                    rest.append(entry)
            if rest:
                kept[action] = rest
        if any(isinstance(v, list) for v in kept.values()):
            operations.append(kept)
    gs.insert("packageOperations", operations)
    return ticked


def boot_disk(gs):
    """On BIOS, puts GRUB on the disk Home Server is installed to. Calamares defaults to the first disk."""
    if os.path.isdir("/sys/firmware/efi"):
        return
    loader = gs.value("bootLoader")
    if not loader or not loader.get("installPath"):
        return
    for part in gs.value("partitions") or []:
        if part.get("mountPoint") == "/":
            sys_path = os.path.realpath("/sys/class/block/" + os.path.basename(part["device"]))
            disk = "/dev/" + os.path.basename(os.path.dirname(sys_path))
            if loader["installPath"] != disk:
                debug("homeserver: boot loader {} -> {}".format(loader["installPath"], disk))
                loader["installPath"] = disk
                gs.insert("bootLoader", loader)
            return


def write(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    os.chmod(path, mode)


def run():
    gs = libcalamares.globalstorage
    root = gs.value("rootMountPoint")
    user = gs.value("username")
    boot_disk(gs)
    cat = catalog.load(os.path.join(CATALOG, "catalog.json"))
    names = catalog.by_name(cat)
    ticked = take_checklist(gs, names)
    picked = {names[name] for name in ticked if name in names}
    drives = sorted(DRIVE.search(name).group(1) for name in ticked if DRIVE.search(name))
    apps = catalog.resolve(cat, picked)
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

    target_catalog = os.path.join(root, "var/lib/homeserver/catalog")
    shutil.rmtree(target_catalog, ignore_errors=True)
    shutil.copytree(CATALOG, target_catalog, ignore=shutil.ignore_patterns("__pycache__"))

    shutil.rmtree(os.path.join(root, "etc/calamares"), ignore_errors=True)
    # Tells installer-scale.sh (on the live system) to power off when the installer closes.
    write("/run/homeserver/installed", "")
    return None
