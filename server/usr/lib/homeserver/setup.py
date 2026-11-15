#!/usr/bin/env python3
"""Configures the apps picked in the installer. Called by configure-apps.sh; every step is safe to repeat.

  setup.py --root DIR prepare    write configs before the containers first start
  setup.py --root DIR connect    link qBittorrent/Sonarr/Radarr/Prowlarr and set up Jellyfin
  setup.py --root DIR seerr      sign Seerr in through Jellyfin and link it to Sonarr/Radarr
  setup.py --root DIR dashboard  write the Homepage config

DIR is the installed system's root: the new disk during install, / afterwards. Every app gets the
name and password typed in the installer.
"""
import argparse
import base64
import hashlib
import http.cookiejar
import json
import os
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
        for name in ("SONARR_KEY", "RADARR_KEY", "PROWLARR_KEY"):
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


def recyclarr_config(s):
    # The TRaSH Guides profiles Recyclarr's own templates use: web-1080p (Sonarr) and
    # hd-bluray-web (Radarr), minus the optional groups that need a personal choice.
    # Naming uses the TRaSH schemes made for Jellyfin.
    return f"""sonarr:
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

radarr:
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


def prepare(ctx):
    for d in ("torrents/movies", "torrents/tv", "media/movies", "media/tv"):
        ctx.mkdir(ctx.data / d)
    ctx.own(ctx.srv, ctx.data, ctx.data / "torrents", ctx.data / "media")
    for d in ("homepage", "filebrowser/database", "filebrowser/config", "jellyfin", "seerr",
              "sonarr", "radarr", "prowlarr", "qbittorrent/qBittorrent", "recyclarr"):
        ctx.mkdir(ctx.appdata / d)
    ctx.own(ctx.appdata / "filebrowser", ctx.appdata / "qbittorrent")

    if "downloads" in ctx.apps:
        for name, port in (("sonarr", 8989), ("radarr", 7878), ("prowlarr", 9696)):
            path = ctx.appdata / name / "config.xml"
            if not path.exists():
                ctx.write(path, arr_config(port, ctx.secrets[name.upper() + "_KEY"], name.capitalize()))
        qbt = ctx.appdata / "qbittorrent/qBittorrent"
        if not (qbt / "qBittorrent.conf").exists():
            ctx.write(qbt / "qBittorrent.conf", qbittorrent_config(ctx.user, ctx.password))
            ctx.write(qbt / "categories.json", json.dumps(
                {"movies": {"save_path": "/data/torrents/movies"}, "tv": {"save_path": "/data/torrents/tv"}}, indent=2))
        ctx.write(ctx.appdata / "recyclarr/recyclarr.yml", recyclarr_config(ctx.secrets))
        (ctx.appdata / "recyclarr/recyclarr.yml").chmod(0o600)

    write_env(ctx.etc / "compose.env", {"PUID": ctx.uid, "PGID": ctx.gid, "TZ": timezone(ctx.root),
                                        "HOMESERVER_HOST": ctx.host}, 0o644)
    dashboard(ctx)


# --- dashboard -----------------------------------------------------------------------------

def dashboard(ctx):
    # Apps appear through their homepage.* container labels; only things that aren't containers
    # are listed here. Homepage reads YAML, and JSON is valid YAML.
    server = [{"Server settings": {"icon": "cockpit.png", "href": f"http://{ctx.host}:9090",
                                   "description": "Updates, disks, restart and shut down"}}]
    if "files" in ctx.apps:
        name = ctx.host.split(".")[0]
        server.append({"Shared folder": {"icon": "samba.png",
                                         "description": f"On Windows, open File Explorer and type \\\\{name}\\Media"}})
    if (ctx.etc / "password-generated").exists() and (ctx.etc / "password").exists():
        server.append({"Your app password": {"icon": "mdi-key", "description": ctx.password}})
    if (ctx.etc / "files-password").exists():
        server.append({"Files password": {"icon": "mdi-key", "description": (ctx.etc / "files-password").read_text()}})

    files = {
        "services.yaml": [{"Server": server}],
        "docker.yaml": {"local": {"socket": "/var/run/docker.sock"}},
        "settings.yaml": {
            "title": "Home Server", "theme": "light", "color": "stone", "headerStyle": "clean",
            "target": "_self", "hideVersion": True, "statusStyle": "dot",
            "layout": {"Watch": {"style": "row", "columns": 2}, "Downloads": {"style": "row", "columns": 4},
                       "Files": {"style": "row", "columns": 1}, "Server": {"style": "row", "columns": 3}}},
        "widgets.yaml": [
            {"greeting": {"text_size": "2xl", "text": "Home Server"}},
            {"resources": {"cpu": True, "memory": True, "disk": "/srv"}},
            {"datetime": {"text_size": "xl", "format": {"dateStyle": "long", "timeStyle": "short"}}}],
        "bookmarks.yaml": [],
    }
    for name, data in files.items():
        ctx.write(ctx.appdata / "homepage" / name, json.dumps(data, indent=2) + "\n")


# --- connect -------------------------------------------------------------------------------

def call(method, url, body=None, headers=None, opener=None) -> Any:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Content-Type": "application/json", "Accept": "application/json", **(headers or {})})
    try:
        with (opener or urllib.request.build_opener()).open(req, timeout=60) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as err:
        sys.exit(f"{method} {url} -> {err.code}: {err.read()[:500].decode(errors='replace')}")
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


def connect_downloads(ctx):
    s = ctx.secrets
    wait("http://localhost:8080")
    for name, port, category_field, category, folder, rename in (
            ("sonarr", 8989, "tvCategory", "tv", "/data/media/tv", "renameEpisodes"),
            ("radarr", 7878, "movieCategory", "movies", "/data/media/movies", "renameMovies")):
        wait(f"http://localhost:{port}/ping")
        api = arr_api(port, s[name.upper() + "_KEY"])
        if not api("GET", "/downloadclient"):
            schema = next(x for x in api("GET", "/downloadclient/schema") if x["implementation"] == "QBittorrent")
            schema.update(name="qBittorrent", enable=True, priority=1)
            fill(schema, host="qbittorrent", port=8080, username=ctx.user, password=ctx.password,
                 **{category_field: category})
            api("POST", "/downloadclient?forceSave=true", schema)
        if not api("GET", "/rootfolder"):
            api("POST", "/rootfolder", {"path": folder})
        # TRaSH Guides media management: hardlinks, subtitles alongside, let custom formats handle propers.
        update_config(api, "mediamanagement", copyUsingHardlinks=True, importExtraFiles=True,
                      extraFileExtensions="srt,ass,ssa,sub,idx", downloadPropersAndRepacks="doNotPrefer",
                      enableMediaInfo=True)
        update_config(api, "naming", **{rename: True})
        set_login(api, ctx)

    wait("http://localhost:9696/ping")
    prowlarr = arr_api(9696, s["PROWLARR_KEY"], "v1")
    have = {a["implementation"] for a in prowlarr("GET", "/applications")}
    for impl, port in (("Sonarr", 8989), ("Radarr", 7878)):
        if impl in have:
            continue
        schema = next(x for x in prowlarr("GET", "/applications/schema") if x["implementation"] == impl)
        schema.update(name=impl, syncLevel="fullSync")
        fill(schema, prowlarrUrl="http://prowlarr:9696", baseUrl=f"http://{impl.lower()}:{port}",
             apiKey=s[impl.upper() + "_KEY"])
        prowlarr("POST", "/applications?forceSave=true", schema)
    set_login(prowlarr, ctx)


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


def connect(ctx):
    if "downloads" in ctx.apps:
        connect_downloads(ctx)
    if "jellyfin" in ctx.apps:
        connect_jellyfin(ctx)


def pick_profile(profiles, preferred):
    for want in preferred:
        for p in profiles:
            if want in p["name"]:
                return p
    return profiles[0]


def seerr(ctx):
    base = "http://localhost:5055/api/v1"
    wait(base + "/status")
    session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    login = {"username": ctx.user, "password": ctx.password}
    if call("GET", base + "/settings/public").get("initialized"):
        call("POST", base + "/auth/jellyfin", login, opener=session)
    else:
        call("POST", base + "/auth/jellyfin", {**login, "hostname": "jellyfin", "port": 8096, "useSsl": False,
                                              "urlBase": "", "email": f"{ctx.user}@{ctx.host}", "serverType": 2},
             opener=session)
        for library in call("POST", base + "/settings/jellyfin/library/sync", opener=session):
            call("PUT", f"{base}/settings/jellyfin/library/{library['id']}", {"enabled": True}, opener=session)

        common = {"useSsl": False, "baseUrl": "", "is4k": False, "isDefault": True, "syncEnabled": False,
                  "preventSearch": False, "tagRequests": False, "tags": []}
        for name, port, folder, preferred, extra in (
                ("sonarr", 8989, "/data/media/tv", ["WEB-1080p", "1080"],
                 {"enableSeasonFolders": True, "animeTags": []}),
                ("radarr", 7878, "/data/media/movies", ["HD Bluray + WEB", "1080"],
                 {"minimumAvailability": "released"})):
            key = ctx.secrets[name.upper() + "_KEY"]
            profile = pick_profile(arr_api(port, key)("GET", "/qualityprofile"), preferred)
            call("POST", f"{base}/settings/{name}", {
                **common, **extra, "name": name.capitalize(), "hostname": name, "port": port, "apiKey": key,
                "activeProfileId": profile["id"], "activeProfileName": profile["name"],
                "activeDirectory": folder, "externalUrl": f"http://{ctx.host}:{port}"}, opener=session)
        call("POST", base + "/settings/initialize", opener=session)

    ctx.secrets["SEERR_KEY"] = call("GET", base + "/settings/main", opener=session)["apiKey"]
    ctx.save_secrets()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/")
    parser.add_argument("step", choices=["prepare", "connect", "seerr", "dashboard"])
    args = parser.parse_args()
    context = Context(args.root)
    {"prepare": prepare, "connect": connect, "seerr": seerr, "dashboard": dashboard}[args.step](context)
