#!/usr/bin/env python3
"""Configures the apps picked in the installer or added later. Called by configure-apps.sh and update.sh;
every step is safe to repeat, and also undoes the links to apps that were removed.

  setup.py --root DIR prepare    write configs before the containers first start
  setup.py --root DIR connect    set up logins, download clients, libraries and Prowlarr
  setup.py --root DIR link       sign Seerr in through Jellyfin and link it to Sonarr/Radarr
                                 (after Recyclarr, so Seerr can use the TRaSH profiles)
  setup.py --root DIR dashboard  write the Homepage config
  setup.py --root DIR look       save the dashboard's title, theme, color and background picture (JSON on
                                 stdin, from the Cockpit page), then write the Homepage config

DIR is the installed system's root: the new disk during install, / afterwards. Every app gets the
name and password typed in the installer (or on the Cockpit page), read from DIR/etc/homeserver/password.
Without that file (an update from the USB stick), the steps that need it are skipped: logins, Jellyfin,
Audiobookshelf and Seerr, and setting up an app for the first time.
"""
import argparse
import base64
import binascii
import hashlib
import http.cookiejar
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

JF_AUTH = 'MediaBrowser Client="homeserver-setup", Device="server", DeviceId="homeserver-setup", Version="1.0"'


def read_env(path):
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"')
    return env


def write_env(path, env, mode=0o600):
    path.write_text("".join(f'{k}="{v}"\n' for k, v in env.items()))
    path.chmod(mode)


class Context:
    def __init__(self, root):
        self.root = Path(root)
        self.etc = self.root / "etc/homeserver"
        self.srv = self.root / "srv"
        self.appdata = self.srv / "appdata"
        self.data = self.srv / "data"
        env = read_env(self.etc / "homeserver.env")
        self.apps = set(env.get("APPS", "").split())
        self.user = env["OWNER"]
        self.uid, self.gid = self.lookup_owner()
        self.host = (self.root / "etc/hostname").read_text().strip() + ".local"
        self.secrets = read_env(self.etc / "secrets.env")
        for name in ("SONARR_KEY", "RADARR_KEY", "PROWLARR_KEY", "CHAPTARR_KEY", "BAZARR_KEY", "SABNZBD_KEY",
                     "SABNZBD_NZB_KEY"):
            self.secrets.setdefault(name, secrets.token_hex(16))
        self.save_secrets()

    def lookup_owner(self):
        for line in (self.root / "etc/passwd").read_text().splitlines():
            fields = line.split(":")
            if fields[0] == self.user:
                return int(fields[2]), int(fields[3])
        sys.exit(f"user {self.user} not found")

    def save_secrets(self):
        write_env(self.etc / "secrets.env", self.secrets)

    @property
    def has_password(self):
        return (self.etc / "password").exists()

    @property
    def password(self):
        return (self.etc / "password").read_text()

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        self.own(path)

    def own(self, *paths):
        for p in paths:
            os.chown(p, self.uid, self.gid)

    def mkdir(self, path):
        path.mkdir(parents=True, exist_ok=True)
        self.own(path)


def timezone(root):
    try:
        return os.readlink(root / "etc/localtime").split("zoneinfo/", 1)[1]
    except (OSError, IndexError):
        return "Etc/UTC"


def language(root):
    lang = read_env(root / "etc/default/locale").get("LANG", "en_US")
    code, _, rest = lang.partition("_")
    return code or "en", (rest[:2] or "US").upper()


# --- prepare -------------------------------------------------------------------------------

def arr_config(port, key, name):
    # Forms login, always required. The username and password are set through the API in connect,
    # because they live in the app's database.
    return f"""<Config>
  <BindAddress>*</BindAddress>
  <Port>{port}</Port>
  <ApiKey>{key}</ApiKey>
  <AuthenticationMethod>Forms</AuthenticationMethod>
  <AuthenticationRequired>Enabled</AuthenticationRequired>
  <UrlBase></UrlBase>
  <UpdateMechanism>Docker</UpdateMechanism>
  <LogLevel>info</LogLevel>
  <InstanceName>{name}</InstanceName>
</Config>
"""


def qbittorrent_config(user, password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha512", password.encode(), salt, 100000)
    hashed = f"{base64.b64encode(salt).decode()}:{base64.b64encode(digest).decode()}"
    # TRaSH Guides: automatic torrent management, so each category saves to its own folder
    # and moves when the category changes.
    return f"""[BitTorrent]
Session\\DefaultSavePath=/data/torrents
Session\\TempPathEnabled=false
Session\\DisableAutoTMMByDefault=false
Session\\DisableAutoTMMTriggers\\CategoryChanged=false
Session\\DisableAutoTMMTriggers\\CategorySavePathChanged=false
Session\\DisableAutoTMMTriggers\\DefaultSavePathChanged=false

[LegalNotice]
Accepted=true

[Preferences]
WebUI\\Username={user}
WebUI\\Password_PBKDF2="@ByteArray({hashed})"
WebUI\\HostHeaderValidation=false
"""


def recyclarr_config(s, apps):
    # The TRaSH Guides profiles Recyclarr's own templates use: web-1080p (Sonarr) and
    # hd-bluray-web (Radarr), minus the optional groups that need a personal choice.
    # Naming uses the TRaSH schemes made for Jellyfin.
    sonarr = f"""sonarr:
  web-1080p:
    base_url: http://sonarr:8989
    api_key: {s["SONARR_KEY"]}
    quality_definition:
      type: series
    quality_profiles:
      - trash_id: 72dae194fc92bf828f32cde7744e51a1  # WEB-1080p
        reset_unmatched_scores:
          enabled: true
    custom_format_groups:
      add:
        - trash_id: 158188097a58d7687dee647e04af0da3  # Golden Rule HD
        - trash_id: 85fae4a2294965b75710ef2989c850eb  # Streaming Services HD/UHD boost
        - trash_id: 59c3af66780d08332fdc64e68297098f  # Unwanted Formats
    media_naming:
      series: jellyfin-tvdb
      season: default
      episodes:
        rename: true
        standard: default
        daily: default
        anime: default
"""
    radarr = f"""radarr:
  hd-bluray-web:
    base_url: http://radarr:7878
    api_key: {s["RADARR_KEY"]}
    quality_definition:
      type: movie
    quality_profiles:
      - trash_id: d1d67249d3890e49bc12e275d989a7e9  # HD Bluray + WEB
        reset_unmatched_scores:
          enabled: true
    custom_format_groups:
      add:
        - trash_id: f8bf8eab4617f12dfdbd16303d8da245  # Golden Rule HD
        - trash_id: a3ac6af01d78e4f21fcb75f601ac96df  # Unwanted Formats
    media_naming:
      folder: jellyfin-tmdb
      movie:
        rename: true
        standard: jellyfin-tmdb
"""
    return "\n".join(part for app, part in (("sonarr", sonarr), ("radarr", radarr)) if app in apps)


def bazarr_config(ctx):
    # Bazarr fills in its defaults around these on first start.
    s = ctx.secrets
    return f"""auth:
  type: form
  username: {ctx.user}
  password: {hashlib.md5(ctx.password.encode()).hexdigest()}
  apikey: {s["BAZARR_KEY"]}
general:
  use_sonarr: {str("sonarr" in ctx.apps).lower()}
  use_radarr: {str("radarr" in ctx.apps).lower()}
sonarr:
  ip: sonarr
  port: 8989
  apikey: {s["SONARR_KEY"]}
radarr:
  ip: radarr
  port: 7878
  apikey: {s["RADARR_KEY"]}
"""


def sabnzbd_config(ctx):
    # TRaSH Guides layout: incomplete downloads apart, finished ones in one folder per category.
    # host_whitelist lists the names it's reached by; IP addresses always work.
    s = ctx.secrets
    names = ", ".join(["sabnzbd", "localhost", ctx.host, ctx.host.split(".")[0]])
    # Without the default category ([[*]]) SABnzbd adds its own defaults on the first start, and its
    # movies and tv replace ours, with no folder.
    categories = "[[*]]\nname = *\norder = 0\npp = 3\nscript = Default\ndir = \"\"\npriority = 0\n" + "".join(
        f"[[{c}]]\nname = {c}\ndir = {c}\npriority = -100\npp = \"\"\nscript = Default\n" for c in CATEGORIES)
    return f"""[misc]
api_key = {s["SABNZBD_KEY"]}
nzb_key = {s["SABNZBD_NZB_KEY"]}
username = {ctx.user}
password = {ctx.password}
html_login = 1
host_whitelist = {names}
download_dir = /data/usenet/incomplete
complete_dir = /data/usenet/complete
permissions = 775
[categories]
{categories}"""


CATEGORIES = {"movies": "movies", "tv": "tv", "books": "books", "audiobooks": "audiobooks", "prowlarr": "prowlarr"}
ARRS = {"sonarr": 8989, "radarr": 7878, "prowlarr": 9696, "chaptarr": 8789}


def prepare(ctx):
    for d in ([f"torrents/{c}" for c in CATEGORIES] + [f"usenet/complete/{c}" for c in CATEGORIES] +
              ["usenet/incomplete"] + [f"media/{m}" for m in ("movies", "tv", "books", "audiobooks", "podcasts")]):
        ctx.mkdir(ctx.data / d)
    ctx.own(ctx.srv, ctx.data, ctx.data / "torrents", ctx.data / "usenet", ctx.data / "usenet/complete", ctx.data / "media")
    for d in ("homepage", "filebrowser/database", "filebrowser/config", "jellyfin", "seerr", "bazarr/config",
              "audiobookshelf/config", "audiobookshelf/metadata", "sabnzbd", "recyclarr", "qbittorrent/qBittorrent",
              "tailscale",
              *ARRS):
        ctx.mkdir(ctx.appdata / d)
    ctx.own(ctx.appdata / "filebrowser", ctx.appdata / "qbittorrent", ctx.appdata / "bazarr",
            ctx.appdata / "audiobookshelf")

    for name, port in ARRS.items():
        path = ctx.appdata / name / "config.xml"
        if name in ctx.apps and not path.exists():
            ctx.write(path, arr_config(port, ctx.secrets[name.upper() + "_KEY"], name.capitalize()))
    qbt = ctx.appdata / "qbittorrent/qBittorrent"
    if "qbittorrent" in ctx.apps and not (qbt / "qBittorrent.conf").exists() and ctx.has_password:
        ctx.write(qbt / "qBittorrent.conf", qbittorrent_config(ctx.user, ctx.password))
        ctx.write(qbt / "categories.json", json.dumps(
            {c: {"save_path": f"/data/torrents/{c}"} for c in CATEGORIES}, indent=2))
    sab = ctx.appdata / "sabnzbd/sabnzbd.ini"
    if "sabnzbd" in ctx.apps and not sab.exists() and ctx.has_password:
        ctx.write(sab, sabnzbd_config(ctx))
        sab.chmod(0o600)
    bazarr = ctx.appdata / "bazarr/config/config.yaml"
    if "bazarr" in ctx.apps and not bazarr.exists() and ctx.has_password:
        ctx.write(bazarr, bazarr_config(ctx))
        bazarr.chmod(0o600)
    elif "bazarr" in ctx.apps and bazarr.exists():
        text = bazarr.read_text()
        for app in ("sonarr", "radarr"):
            text = re.sub(rf"^(\s+use_{app}:) \w+$", rf"\1 {str(app in ctx.apps).lower()}", text, flags=re.M)
        bazarr.write_text(text)
    if "recyclarr" in ctx.apps:
        ctx.write(ctx.appdata / "recyclarr/recyclarr.yml", recyclarr_config(ctx.secrets, ctx.apps))
        (ctx.appdata / "recyclarr/recyclarr.yml").chmod(0o600)

    write_env(ctx.etc / "compose.env", {"PUID": ctx.uid, "PGID": ctx.gid, "TZ": timezone(ctx.root),
                                        "HOMESERVER_HOST": ctx.host}, 0o644)
    dashboard(ctx)


# --- dashboard -----------------------------------------------------------------------------

# What the Cockpit page can change about the dashboard. /etc/homeserver/dashboard.json holds the choices.
LOOK_DEFAULTS = {"title": "Home Server", "theme": "light", "color": "stone", "background": ""}
COLORS = ["slate", "gray", "zinc", "neutral", "stone", "red", "orange", "amber", "yellow", "lime", "green",
          "emerald", "teal", "cyan", "sky", "blue", "indigo", "violet", "purple", "fuchsia", "pink", "rose"]
PICTURES = {b"\xff\xd8\xff": "jpg", b"\x89PNG": "png", b"RIFF": "webp"}
BACKGROUNDS = Path(__file__).resolve().parent / "backgrounds"


def read_look(ctx):
    try:
        saved = json.loads((ctx.etc / "dashboard.json").read_text())
    except (OSError, ValueError):
        saved = {}
    return {k: saved.get(k, v) for k, v in LOOK_DEFAULTS.items()}


def look(ctx):
    """{"title", "theme", "color", "background": "keep" | "remove" | "builtin:<name>" | base64 picture} on stdin."""
    new = json.load(sys.stdin)
    current = read_look(ctx)
    title = str(new.get("title", current["title"])).strip()[:60] or LOOK_DEFAULTS["title"]
    theme = new.get("theme") if new.get("theme") in ("light", "dark") else current["theme"]
    color = new.get("color") if new.get("color") in COLORS else current["color"]
    background = current["background"]
    images = ctx.appdata / "homepage/images"
    picture = new.get("background", "keep")
    data = None
    if picture.startswith("builtin:"):
        # One of the pictures that come with the catalog (backgrounds/), for the server's own screen,
        # which can't open a file window.
        source = BACKGROUNDS / (picture[8:] + ".jpg")
        if "/" in picture or not source.is_file():
            sys.exit("That picture isn't one of the built-in ones")
        data, name = source.read_bytes(), f"builtin-{source.name}"
    elif picture not in ("keep", "remove", ""):
        try:
            data = base64.b64decode(picture, validate=True)
        except (binascii.Error, ValueError):
            sys.exit("That picture couldn't be read")
        if len(data) > 15 * 1024 * 1024:
            sys.exit("That picture is too big (15 MB at most)")
        ext = next((e for magic, e in PICTURES.items() if data.startswith(magic)), None)
        if not ext or (ext == "webp" and data[8:12] != b"WEBP"):
            sys.exit("Use a JPEG, PNG or WebP picture")
        name = f"background.{ext}"
    if picture == "remove" or data:
        for old in [*images.glob("background.*"), *images.glob("builtin-*")]:
            old.unlink()
        background = ""
    if data:
        ctx.mkdir(images)
        path = images / name
        path.write_bytes(data)
        ctx.own(path)
        background = path.name
    saved = {"title": title, "theme": theme, "color": color, "background": background}
    (ctx.etc / "dashboard.json").write_text(json.dumps(saved, indent=2) + "\n")
    (ctx.etc / "dashboard.json").chmod(0o644)
    dashboard(ctx)
    print("Saved. Reload Homepage (the dashboard with the app tiles, F5) in a few seconds to see it.")


def dashboard(ctx):
    # Apps appear through their homepage.* container labels; only things that aren't containers
    # are listed here. Homepage reads YAML, and JSON is valid YAML.
    style = read_look(ctx)
    server = [{"Server settings": {"icon": "cockpit.png", "href": f"http://{ctx.host}:9090",
                                   "description": "Updates, disks, restart and shut down"}},
              {"Apps": {"icon": "mdi-apps", "href": f"http://{ctx.host}:9090/homeserver",
                        "description": "Add, remove and update your apps"}}]
    if "tailscale" in ctx.apps:
        server.append({"Remote access": {"icon": "tailscale.png", "href": f"http://{ctx.host}:9090/homeserver",
                                         "description": "Use your apps away from home with Tailscale"}})
    if "files" in ctx.apps:
        name = ctx.host.split(".")[0]
        server.append({"Shared folder": {"icon": "mdi-folder-network",
                                         "description": f"On Windows, open File Explorer and type \\\\{name}\\Media"}})
    if (ctx.etc / "password-generated").exists() and (ctx.etc / "password").exists():
        server.append({"Your app password": {"icon": "mdi-key", "description": ctx.password}})
    if (ctx.etc / "files-password").exists():
        server.append({"Files password": {"icon": "mdi-key", "description": (ctx.etc / "files-password").read_text()}})

    files = {
        "services.yaml": [{"Server": server}],
        "docker.yaml": {"local": {"socket": "/var/run/docker.sock"}},
        "settings.yaml": {
            "title": style["title"], "theme": style["theme"], "color": style["color"], "headerStyle": "clean",
            "target": "_blank", "hideVersion": True, "statusStyle": "dot",
            "layout": {"Watch": {"style": "row", "columns": 2}, "Downloads": {"style": "row", "columns": 4},
                       "Files": {"style": "row", "columns": 1}, "Server": {"style": "row", "columns": 3}}},
        "widgets.yaml": [
            {"greeting": {"text_size": "2xl", "text": style["title"]}},
            {"resources": {"cpu": True, "memory": True, "disk": "/srv/data"}},
            {"datetime": {"text_size": "xl", "format": {"dateStyle": "long", "timeStyle": "short"}}}],
        "bookmarks.yaml": [],
    }
    if style["background"]:
        files["settings.yaml"]["background"] = {"image": "/images/" + style["background"], "blur": "sm",
                                                "brightness": 75}
        files["settings.yaml"]["cardBlur"] = "md"
    ctx.mkdir(ctx.appdata / "homepage/images")
    for name, data in files.items():
        ctx.write(ctx.appdata / "homepage" / name, json.dumps(data, indent=2) + "\n")
    ctx.write(ctx.appdata / "homepage/custom.js", RELOAD_ON_ERRORS + SAME_HOST_LINKS.replace("HOST", ctx.host))


# The tiles link to http://<name>.local:<port>. Opened from another address (the server's own screen
# uses localhost, a phone may use the IP address), that's another site to the browser, and Cockpit's
# login cookie (SameSite=Strict) is then dropped right after logging in, which sends you back to the
# login page. So a click goes to the same address the dashboard was opened with.
SAME_HOST_LINKS = """for (const type of ["click", "auxclick"]) {
  document.addEventListener(type, event => {
    const link = event.target.closest && event.target.closest("a[href]");
    if (!link) return;
    const url = new URL(link.href, location.href);
    if (url.hostname === "HOST" && location.hostname !== "HOST") {
      url.hostname = location.hostname;
      link.href = url.href;
    }
  }, true);
}
"""


# Right after boot some apps are still starting and answer with errors, and Homepage widgets don't
# retry. Reload the page a minute later while any widget shows an error (at most 10 times per tab).
RELOAD_ON_ERRORS = """setInterval(() => {
  const reloads = Number(sessionStorage.getItem("homeserver-reloads") || 0);
  if (reloads < 10 && document.body.innerText.includes("API Error")) {
    sessionStorage.setItem("homeserver-reloads", reloads + 1);
    location.reload();
  }
}, 60000);
"""


# --- connect -------------------------------------------------------------------------------

def call(method, url, body=None, headers=None, opener=None, allow_error=False) -> Any:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Content-Type": "application/json", "Accept": "application/json", **(headers or {})})
    try:
        with (opener or urllib.request.build_opener()).open(req, timeout=60) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as err:
        if not allow_error:
            sys.exit(f"{method} {url} -> {err.code}: {err.read()[:500].decode(errors='replace')}")
        raw = err.read()
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return raw.decode()


def wait(url, timeout=900):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=5)
            return
        except urllib.error.HTTPError as err:
            if err.code < 500:
                return
        except OSError:
            pass
        time.sleep(3)
    sys.exit(f"timed out waiting for {url}")


def field(item, name):
    return next((f.get("value") for f in item["fields"] if f["name"] == name), None)


def fill(schema, **values):
    for field in schema["fields"]:
        if field["name"] in values:
            field["value"] = values[field["name"]]
    return schema


def arr_api(port, key, version="v3"):
    def api(method, path, body=None):
        return call(method, f"http://localhost:{port}/api/{version}{path}", body, {"X-Api-Key": key})
    return api


def update_config(api, section, **values):
    config = api("GET", f"/config/{section}")
    config.update({k: v for k, v in values.items() if k in config})
    api("PUT", f"/config/{section}/{config['id']}", config)


def set_login(api, ctx):
    update_config(api, "host", authenticationMethod="forms", authenticationRequired="enabled",
                  username=ctx.user, password=ctx.password, passwordConfirmation=ctx.password)


def download_clients(ctx, api, categories):
    """Adds the installed download apps to an arr (or Prowlarr) and drops removed ones."""
    clients = {"qbittorrent": ("QBittorrent", "qBittorrent", lambda: {"username": ctx.user, "password": ctx.password}),
               "sabnzbd": ("Sabnzbd", "SABnzbd", lambda: {"apiKey": ctx.secrets["SABNZBD_KEY"]})}
    for client in api("GET", "/downloadclient"):
        if field(client, "host") in clients and field(client, "host") not in ctx.apps:
            api("DELETE", f"/downloadclient/{client['id']}")
    have = {c["implementation"] for c in api("GET", "/downloadclient")}
    for app, (impl, label, login) in clients.items():
        if app not in ctx.apps or impl in have or (app == "qbittorrent" and not ctx.has_password):
            continue
        schema = next(x for x in api("GET", "/downloadclient/schema") if x["implementation"] == impl)
        schema.update(name=label, enable=True, priority=1)
        fill(schema, host=app, port=8080, **login(), **categories)
        api("POST", "/downloadclient?forceSave=true", schema)


def connect_arr(ctx, name):
    port = ARRS[name]
    version = "v1" if name == "chaptarr" else "v3"
    wait(f"http://localhost:{port}/ping")
    api = arr_api(port, ctx.secrets[name.upper() + "_KEY"], version)
    categories = {"sonarr": {"tvCategory": "tv"}, "radarr": {"movieCategory": "movies"},
                  "chaptarr": {"audiobookCategory": "audiobooks", "ebookCategory": "books"}}[name]
    download_clients(ctx, api, categories)

    if not api("GET", "/rootfolder"):
        if name == "chaptarr":
            quality = {p["name"]: p["id"] for p in api("GET", "/qualityprofile")}
            metadata = {p["name"]: p["id"] for p in api("GET", "/metadataprofile")}
            # folderType 1 = audiobooks only, 2 = ebooks only; each takes only its own profiles.
            for label, path, kind, prefix, q, m in (
                    ("Audiobooks", "/data/media/audiobooks", 1, "audiobook", "Audiobook", "Audiobook Default"),
                    ("Books", "/data/media/books", 2, "ebook", "E-Book", "Ebook Default")):
                api("POST", "/rootfolder", {
                    "name": label, "path": path, "folderType": kind, "isCalibreLibrary": False,
                    f"{prefix}QualityProfileId": quality.get(q, 1), f"{prefix}MetadataProfileId": metadata.get(m, 1),
                    "defaultMonitorOption": "all", "defaultNewItemMonitorOption": "all"})
        else:
            api("POST", "/rootfolder", {"path": {"sonarr": "/data/media/tv", "radarr": "/data/media/movies"}[name]})

    if name in ("sonarr", "radarr"):
        # TRaSH Guides media management: hardlinks, subtitles alongside, let custom formats handle propers.
        update_config(api, "mediamanagement", copyUsingHardlinks=True, importExtraFiles=True,
                      extraFileExtensions="srt,ass,ssa,sub,idx", downloadPropersAndRepacks="doNotPrefer",
                      enableMediaInfo=True)
        update_config(api, "naming", **{"renameEpisodes" if name == "sonarr" else "renameMovies": True})
    if ctx.has_password:
        set_login(api, ctx)


def connect_prowlarr(ctx):
    wait("http://localhost:9696/ping")
    prowlarr = arr_api(9696, ctx.secrets["PROWLARR_KEY"], "v1")
    schemas = {x["implementation"]: x for x in prowlarr("GET", "/applications/schema")}
    for app in prowlarr("GET", "/applications"):
        if any(field(app, "baseUrl") == f"http://{name}:{ARRS[name]}" and name not in ctx.apps
               for name in ("sonarr", "radarr", "chaptarr")):
            prowlarr("DELETE", f"/applications/{app['id']}")
    have = {a["name"] for a in prowlarr("GET", "/applications")}
    for name in ("sonarr", "radarr", "chaptarr"):
        label = name.capitalize()
        if name not in ctx.apps or label in have:
            continue
        # Chaptarr speaks Readarr's API; Prowlarr may not know it by name.
        schema = schemas.get(label) or schemas.get("Readarr")
        schema.update(name=label, syncLevel="fullSync")
        fill(schema, prowlarrUrl="http://prowlarr:9696", baseUrl=f"http://{name}:{ARRS[name]}",
             apiKey=ctx.secrets[name.upper() + "_KEY"])
        prowlarr("POST", "/applications?forceSave=true", schema)
    # For grabbing straight from a Prowlarr search (what the arrs don't find): its own folder, never imported.
    download_clients(ctx, prowlarr, {"category": "prowlarr"})
    if ctx.has_password:
        set_login(prowlarr, ctx)


def connect_audiobookshelf(ctx):
    base = "http://localhost:13378"
    wait(base + "/status")
    if not call("GET", base + "/status").get("isInit"):
        call("POST", base + "/init", {"newRoot": {"username": ctx.user, "password": ctx.password}})
    user = call("POST", base + "/login", {"username": ctx.user, "password": ctx.password})["user"]
    auth = {"Authorization": "Bearer " + (user.get("accessToken") or user["token"])}
    have = {lib["name"] for lib in call("GET", base + "/api/libraries", headers=auth)["libraries"]}
    for name, path, kind in (("Audiobooks", "/data/media/audiobooks", "book"), ("Books", "/data/media/books", "book"),
                             ("Podcasts", "/data/media/podcasts", "podcast")):
        if name not in have:
            call("POST", base + "/api/libraries", {"name": name, "folders": [{"fullPath": path}], "mediaType": kind},
                 auth)
    if not ctx.secrets.get("AUDIOBOOKSHELF_KEY"):
        key = call("POST", base + "/api/api-keys", {"name": "Dashboard", "userId": user["id"], "isActive": True}, auth)
        ctx.secrets["AUDIOBOOKSHELF_KEY"] = key["apiKey"]["apiKey"]
        ctx.save_secrets()


def connect_jellyfin(ctx):
    base = "http://localhost:8096"
    wait(base + "/health")
    if not call("GET", base + "/System/Info/Public").get("StartupWizardCompleted"):
        lang, country = language(ctx.root)
        call("POST", base + "/Startup/Configuration",
             {"UICulture": "en-US", "MetadataCountryCode": country, "PreferredMetadataLanguage": lang})
        call("GET", base + "/Startup/User")
        call("POST", base + "/Startup/User", {"Name": ctx.user, "Password": ctx.password})
        call("POST", base + "/Startup/RemoteAccess", {"EnableRemoteAccess": True, "EnableAutomaticPortMapping": False})
        call("POST", base + "/Startup/Complete")

    token = call("POST", base + "/Users/AuthenticateByName", {"Username": ctx.user, "Pw": ctx.password},
                 {"Authorization": JF_AUTH})["AccessToken"]
    auth = {"Authorization": f'{JF_AUTH}, Token="{token}"'}
    have = {f["Name"] for f in call("GET", base + "/Library/VirtualFolders", headers=auth)}
    for name, kind, path in (("Movies", "movies", "/data/media/movies"), ("Shows", "tvshows", "/data/media/tv")):
        if name not in have:
            query = urllib.parse.urlencode({"name": name, "collectionType": kind, "paths": path, "refreshLibrary": "true"})
            call("POST", f"{base}/Library/VirtualFolders?{query}", {"LibraryOptions": {}}, auth)

    def dashboard_key():
        items = call("GET", base + "/Auth/Keys", headers=auth)["Items"]
        return next((k["AccessToken"] for k in items if k["AppName"] == "Dashboard"), None)

    if not dashboard_key():
        call("POST", base + "/Auth/Keys?app=Dashboard", headers=auth)
    ctx.secrets["JELLYFIN_KEY"] = dashboard_key()
    ctx.save_secrets()


# Subtitle sources that need no account; the owner can add others (OpenSubtitles, with an account).
BAZARR_PROVIDERS = ["embeddedsubtitles", "gestdown", "tvsubtitles", "yifysubtitles"]


def connect_bazarr(ctx):
    # Without a languages profile Bazarr fetches nothing. One profile (the installer's language plus
    # English), the default for new shows and movies and given to those that have none; only when
    # Bazarr has no profile yet, since saving profiles replaces all of them.
    base = "http://localhost:6767/api"
    wait(base + "/system/ping")
    headers = {"X-API-KEY": ctx.secrets["BAZARR_KEY"]}

    def post(path, fields):
        body = urllib.parse.urlencode(fields, doseq=True).encode()
        req = urllib.request.Request(base + path, data=body, method="POST", headers={
            **headers, "Content-Type": "application/x-www-form-urlencoded"})
        urllib.request.urlopen(req, timeout=60).read()

    get = lambda path: call("GET", base + path, headers=headers)
    general = get("/system/settings")["general"]
    if not general.get("enabled_providers"):
        post("/system/settings", {"settings-general-enabled_providers": BAZARR_PROVIDERS})
    if get("/system/languages/profiles"):
        return
    known = {lang["code2"] for lang in get("/system/languages")}
    codes = [c for c in dict.fromkeys([language(ctx.root)[0], "en"]) if c in known]
    profile = {"profileId": 1, "name": "Default", "cutoff": None, "mustContain": [], "mustNotContain": [],
               "originalFormat": False, "tag": None,
               "items": [{"id": i + 1, "language": c, "audio_exclude": "False", "hi": "False", "forced": "False"}
                         for i, c in enumerate(codes)]}
    post("/system/settings", {"languages-enabled": codes, "languages-profiles": json.dumps([profile]),
                              "settings-general-serie_default_enabled": "true",
                              "settings-general-serie_default_profile": "1",
                              "settings-general-movie_default_enabled": "true",
                              "settings-general-movie_default_profile": "1"})
    for kind, key in (("series", "sonarrSeriesId"), ("movies", "radarrId")):
        items = [i[key] for i in get(f"/{kind}?start=0&length=-1")["data"] if i.get("profileId") is None]
        if items:
            post(f"/{kind}", {"seriesid" if kind == "series" else "radarrid": items, "profileid": ["1"] * len(items)})


def connect_sabnzbd(ctx):
    # sabnzbd.ini is only written at install; categories added to the catalog later reach older
    # servers here. Servers installed before catalog 10 also got SABnzbd's own movies and tv
    # categories, with no folder (see sabnzbd_config). Ones the owner made are left alone.
    api = f"http://localhost:8090/api?apikey={ctx.secrets['SABNZBD_KEY']}&output=json"
    have = {c["name"]: c["dir"] for c in call("GET", api + "&mode=get_config&section=categories")["config"]["categories"]}
    for name in CATEGORIES:
        if not have.get(name):
            call("GET", api + f"&mode=set_config&section=categories&keyword={name}&dir={name}&priority=-100")


def connect(ctx):
    if "qbittorrent" in ctx.apps:
        wait("http://localhost:8080")
    if "sabnzbd" in ctx.apps:
        wait("http://localhost:8090")
        connect_sabnzbd(ctx)
    for name in ("sonarr", "radarr", "chaptarr"):
        if name in ctx.apps:
            connect_arr(ctx, name)
    steps = {"prowlarr": connect_prowlarr, "bazarr": connect_bazarr, "jellyfin": connect_jellyfin,
             "audiobookshelf": connect_audiobookshelf}
    for name, step in steps.items():
        if name in ctx.apps and (name in ("prowlarr", "bazarr") or ctx.has_password):
            step(ctx)


def link(ctx):
    if "seerr" in ctx.apps and ctx.has_password:
        connect_seerr(ctx)


def pick_profile(profiles, preferred):
    for want in preferred:
        for p in profiles:
            if want in p["name"]:
                return p
    return profiles[0]


def connect_seerr(ctx):
    base = "http://localhost:5055/api/v1"
    wait(base + "/status")
    session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    login = {"username": ctx.user, "password": ctx.password}
    initialized = call("GET", base + "/settings/public").get("initialized")
    if initialized:
        call("POST", base + "/auth/jellyfin", login, opener=session)
    else:
        call("POST", base + "/auth/jellyfin", {**login, "hostname": "jellyfin", "port": 8096, "useSsl": False,
                                              "urlBase": "", "email": f"{ctx.user}@{ctx.host}", "serverType": 2},
             opener=session)
        for library in call("POST", base + "/settings/jellyfin/library/sync", opener=session):
            call("PUT", f"{base}/settings/jellyfin/library/{library['id']}", {"enabled": True}, opener=session)

    # Sonarr and Radarr as installed now: added if new, dropped if removed.
    common = {"useSsl": False, "baseUrl": "", "is4k": False, "isDefault": True, "syncEnabled": False,
              "preventSearch": False, "tagRequests": False, "tags": []}
    for name, port, folder, preferred, extra in (
            ("sonarr", 8989, "/data/media/tv", ["WEB-1080p", "1080"],
             {"enableSeasonFolders": True, "animeTags": []}),
            ("radarr", 7878, "/data/media/movies", ["HD Bluray + WEB", "1080"],
             {"minimumAvailability": "released"})):
        ours = [s for s in call("GET", f"{base}/settings/{name}", opener=session) if s.get("hostname") == name]
        if name not in ctx.apps:
            for server in ours:
                call("DELETE", f"{base}/settings/{name}/{server['id']}", opener=session)
            continue
        key = ctx.secrets[name.upper() + "_KEY"]
        profile = pick_profile(arr_api(port, key)("GET", "/qualityprofile"), preferred)
        if ours:
            # Linked before Recyclarr's profiles existed (no internet then): moved to the TRaSH profile
            # once it's there. A profile the owner picked stays.
            server = ours[0]
            if server.get("activeProfileName") == "HD-1080p" and profile["name"] == preferred[0]:
                body = {k: v for k, v in server.items() if k != "id"}
                body.update(activeProfileId=profile["id"], activeProfileName=profile["name"])
                call("PUT", f"{base}/settings/{name}/{server['id']}", body, opener=session)
            continue
        call("POST", f"{base}/settings/{name}", {
            **common, **extra, "name": name.capitalize(), "hostname": name, "port": port, "apiKey": key,
            "activeProfileId": profile["id"], "activeProfileName": profile["name"],
            "activeDirectory": folder, "externalUrl": f"http://{ctx.host}:{port}"}, opener=session)
    if not initialized:
        call("POST", base + "/settings/initialize", opener=session)

    ctx.secrets["SEERR_KEY"] = call("GET", base + "/settings/main", opener=session)["apiKey"]
    ctx.save_secrets()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/")
    steps = {"prepare": prepare, "connect": connect, "link": link, "dashboard": dashboard, "look": look}
    parser.add_argument("step", choices=list(steps))
    args = parser.parse_args()
    steps[args.step](Context(args.root))
