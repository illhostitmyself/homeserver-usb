#!/usr/bin/env python3
"""The app list and its rules, from catalog.json. Imported by the installer's homeserver step.

  apps.py installer DIR   write the installer's checklist (DIR/netinstall-apps.yaml) and the
                          Review page's sizes (DIR/catalog.js)
  apps.py store           JSON for the Cockpit page: every app, and which are installed
  apps.py plan APP...     JSON: what installing exactly these apps (plus what they need) adds and removes
  apps.py resolve APP...  the apps to install for these, space-separated (for apps.sh)
  apps.py names APP...    their display names, comma-separated
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(path=HERE / "catalog.json"):
    return json.loads(Path(path).read_text())


def always(cat):
    """Apps every server gets, whatever was ticked."""
    return {a for g in cat["groups"] if g.get("always") for a in g["apps"]}


def by_name(cat):
    return {app["name"]: app_id for app_id, app in cat["apps"].items()}


def resolve(cat, picked):
    """The picked apps plus what they need, and the ones every server gets. Only container apps
    (not the system parts like Cockpit) are returned."""
    apps = set(picked) | always(cat)
    changed = True
    while changed:
        before = set(apps)
        for app_id in list(apps):
            app = cat["apps"].get(app_id, {})
            apps.update(app.get("needs", []))
            one_of = app.get("needs_one_of")
            if one_of and not apps.intersection(one_of["options"]):
                apps.update(one_of["add"])
        changed = apps != before
    return sorted(a for a in apps if a in cat["apps"] and not cat["apps"][a].get("system"))


def installed(root="/"):
    """The apps on this server, from /etc/homeserver/homeserver.env."""
    env = Path(root, "etc/homeserver/homeserver.env")
    for line in env.read_text().splitlines() if env.exists() else []:
        if line.startswith("APPS="):
            return set(line.split("=", 1)[1].strip().strip('"').split())
    return set()


def needed_by(cat, apps, app_id):
    """Names of the apps in `apps` that `app_id` is there for."""
    names = []
    for other in sorted(apps):
        app = cat["apps"][other]
        one_of = app.get("needs_one_of", {})
        if app_id in app.get("needs", []) or app_id in one_of.get("add", []) or app_id in one_of.get("options", []):
            names.append(app["name"])
    return names


def plan(cat, wanted):
    have = installed()
    apps = set(resolve(cat, wanted))
    return {"apps": sorted(apps), "add": sorted(apps - have), "remove": sorted(have - apps),
            "needed": {a: needed_by(cat, apps, a) for a in sorted(apps - set(wanted) - always(cat))}}


def store(cat):
    always_ids = always(cat)
    return {"version": cat["version"], "installed": sorted(installed()),
            "groups": [{"name": g["name"], "description": g["description"], "always": bool(g.get("always")),
                        "apps": [{"id": a, **cat["apps"][a], "always": a in always_ids} for a in g["apps"]]}
                       for g in cat["groups"]]}


def quote(text):
    return json.dumps(text)


def installer(cat, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    lines = []
    for group in cat["groups"]:
        lines += [f"- name: {quote(group['name'])}", f"  description: {quote(group['description'])}",
                  "  selected: true", "  expanded: true"]
        if group.get("always"):
            lines.append("  immutable: true")
        lines.append("  packages:")
        for app_id in group["apps"]:
            app = cat["apps"][app_id]
            lines += [f"    - name: {quote(app['name'])}", f"      description: {quote(app['description'])}"]
    (out / "netinstall-apps.yaml").write_text("\n".join(lines) + "\n")
    # Checklist name -> [download MB, disk MB, memory MB when idle], for review.qml.
    cost = {app["name"]: app["cost"] for app in cat["apps"].values() if "cost" in app}
    (out / "catalog.js").write_text(".pragma library\nvar cost = " + json.dumps(cost) + ";\n")


if __name__ == "__main__":
    cmd, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])
    cat = load()
    unknown = [a for a in args if a not in cat["apps"]] if cmd in ("plan", "resolve", "names") else []
    if unknown:
        sys.exit("unknown app: " + " ".join(unknown))
    if cmd == "installer" and len(args) == 1:
        installer(cat, args[0])
    elif cmd == "store":
        print(json.dumps(store(cat)))
    elif cmd == "plan":
        print(json.dumps(plan(cat, args)))
    elif cmd == "resolve":
        print(" ".join(resolve(cat, args)))
    elif cmd == "names":
        print(", ".join(cat["apps"][a]["name"] for a in args))
    else:
        sys.exit(__doc__)
