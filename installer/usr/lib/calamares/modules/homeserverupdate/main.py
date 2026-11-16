import os

import libcalamares
from libcalamares.utils import debug, warning

# update-system.sh's step lines -> how far along the bar each one starts.
STEPS = {
    "Opening your server's disk...": 0.05,
    "Adding new system packages...": 0.15,
    "Updating Home Server...": 0.85,
}
status = "Updating your server"
lines = []


def pretty_name():
    return "Updating your server"


def pretty_status_message():
    return status


def on_line(line):
    global status
    lines.append(line)
    debug("update: " + line)
    text = line.strip()
    if text in STEPS:
        status = text.rstrip(".")
        libcalamares.job.setprogress(STEPS[text])


def run():
    dev = os.environ.get("HS_DEV")
    if not dev:
        return ("No Home Server found", "Restart the computer with the USB stick in to try again.")
    try:
        # Depending on the Calamares version a failed command raises or returns its exit code.
        rc = libcalamares.utils.host_env_process_output(["/usr/lib/homeserver/update-system.sh", dev], on_line)
        failed = isinstance(rc, int) and rc != 0
    except Exception as e:
        warning("homeserverupdate: {}".format(e))
        failed = True
    if failed:
        shown = [l for l in lines if l.strip() and not l.startswith("==")][-12:]
        return ("The update didn't finish",
                "Nothing was erased. Your server still starts as before.\n\n" + "\n".join(shown))
    libcalamares.job.setprogress(1.0)
    # Tells installer-scale.sh to restart instead of starting the installer.
    open("/run/homeserver/updated", "w").close()
    return None
