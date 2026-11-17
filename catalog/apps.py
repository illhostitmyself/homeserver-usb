#!/usr/bin/env python3
"""The app list and its rules, from catalog.json. Imported by the installer's homeserver step.

  apps.py installer DIR   write the installer's checklist (DIR/netinstall-apps.yaml) and the
                          Review page's sizes (DIR/catalog.js)
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
    if len(sys.argv) == 3 and sys.argv[1] == "installer":
        installer(load(), sys.argv[2])
    else:
        sys.exit(__doc__)
