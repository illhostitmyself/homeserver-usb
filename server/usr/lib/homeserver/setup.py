#!/usr/bin/env python3
"""First-start setup for the apps picked in the installer.

prepare: writes each app's config before its container starts (API keys, logins, paths).
connect: once the containers are up, links them through their APIs. Safe to run again.
"""
import base64
import hashlib
import http.cookiejar
import json
import os
import pwd
import secrets
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ETC = Path("/etc/homeserver")
DATA = Path("/srv/homeserver")
MEDIA = Path("/srv/media")
MEDIA_DIRS = ["Movies", "TV Shows", "Downloads"]
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


def write(path, text, uid, gid):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    os.chown(path, uid, gid)


class Context:
    def __init__(self):
        self.env = read_env(ETC / "homeserver.env")
        self.apps = set(self.env.get("APPS", "").split())
        self.user = self.env["OWNER"]
        owner = pwd.getpwnam(self.user)
        self.uid, self.gid = owner.pw_uid, owner.pw_gid
        self.host = socket.gethostname() + ".local"
        self.secrets = read_env(ETC / "secrets.env")
        for name in ("SONARR_KEY", "RADARR_KEY", "PROWLARR_KEY"):
            self.secrets.setdefault(name, secrets.token_hex(16))
        self.secrets.setdefault("QBIT_PASSWORD", secrets.token_urlsafe(12))
        self.save_secrets()

    def save_secrets(self):
        write_env(ETC / "secrets.env", self.secrets)

    @property
    def password(self):
        owner = ETC / "owner-password"
        if owner.exists():
            return owner.read_text()
        generated = ETC / "app-password"
        if not generated.exists():
            generated.write_text(secrets.token_urlsafe(9))
            generated.chmod(0o600)
        return generated.read_text()

    @property
    def generated_password(self):
        path = ETC / "app-password"
        return path.read_text() if path.exists() else None


def timezone():
    try:
        return os.readlink("/etc/localtime").split("zoneinfo/", 1)[1]
    except (OSError, IndexError):
        return "Etc/UTC"


def language():
    lang = read_env(Path("/etc/default/locale")).get("LANG", "en_US")
    code, _, rest = lang.partition("_")
    return code or "en", (rest[:2] or "US").upper()


# --- prepare -------------------------------------------------------------------------------

def arr_config(port, key, name):
    # External auth = no login screen; these apps are only reachable from the home network.
    return f"""<Config>
  <BindAddress>*</BindAddress>
  <Port>{port}</Port>
  <ApiKey>{key}</ApiKey>
  <AuthenticationMethod>External</AuthenticationMethod>
  <AuthenticationRequired>DisabledForLocalAddresses</AuthenticationRequired>
  <UrlBase></UrlBase>
  <UpdateMechanism>Docker</UpdateMechanism>
  <LogLevel>info</LogLevel>
  <InstanceName>{name}</InstanceName>
</Config>
"""


def qbittorrent_config(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha512", password.encode(), salt, 100000)
    hashed = f"{base64.b64encode(salt).decode()}:{base64.b64encode(digest).decode()}"
    return f"""[BitTorrent]
Session\\DefaultSavePath=/data/Downloads/
Session\\TempPathEnabled=false

[LegalNotice]
Accepted=true

[Preferences]
WebUI\\Username=admin
WebUI\\Password_PBKDF2="@ByteArray({hashed})"
WebUI\\AuthSubnetWhitelistEnabled=true
WebUI\\AuthSubnetWhitelist=10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
WebUI\\HostHeaderValidation=false
"""


def prepare(ctx):
    ctx.password  # creates app-password when the installer couldn't pass one on; firstboot.sh needs it for Samba
    for d in [MEDIA, *(MEDIA / m for m in MEDIA_DIRS)]:
        d.mkdir(parents=True, exist_ok=True)
        os.chown(d, ctx.uid, ctx.gid)
    DATA.mkdir(parents=True, exist_ok=True)

    if "downloads" in ctx.apps:
        for name, port in (("sonarr", 8989), ("radarr", 7878), ("prowlarr", 9696)):
            path = DATA / name / "config.xml"
            if not path.exists():
                write(path, arr_config(port, ctx.secrets[name.upper() + "_KEY"], name.capitalize()), ctx.uid, ctx.gid)
                os.chown(path.parent, ctx.uid, ctx.gid)
        qbt = DATA / "qbittorrent" / "qBittorrent" / "qBittorrent.conf"
        if not qbt.exists():
            write(qbt, qbittorrent_config(ctx.secrets["QBIT_PASSWORD"]), ctx.uid, ctx.gid)
            for d in (qbt.parent, qbt.parent.parent):
                os.chown(d, ctx.uid, ctx.gid)

    for name in ("jellyfin", "seerr", "homepage"):
        d = DATA / name
        d.mkdir(exist_ok=True)
        os.chown(d, ctx.uid, ctx.gid)

    write_env(ETC / "compose.env", {"PUID": ctx.uid, "PGID": ctx.gid, "TZ": timezone()}, 0o644)
    write_homepage(ctx)


# --- dashboard -----------------------------------------------------------------------------

def write_homepage(ctx):
    s, host = ctx.secrets, ctx.host
    groups = []
    watch = []
    if "jellyfin" in ctx.apps:
        tile: dict[str, Any] = {"icon": "jellyfin.png", "href": f"http://{host}:8096", "description": "Watch your movies and shows"}
        if s.get("JELLYFIN_KEY"):
            tile["widget"] = {"type": "jellyfin", "url": "http://jellyfin:8096", "key": s["JELLYFIN_KEY"],
                              "enableBlocks": True, "enableNowPlaying": True}
        watch.append({"Movies & TV": tile})
    if "requests" in ctx.apps:
        tile: dict[str, Any] = {"icon": "jellyseerr.png", "href": f"http://{host}:5055", "description": "Ask for a movie or show"}
        if s.get("SEERR_KEY"):
            tile["widget"] = {"type": "jellyseerr", "url": "http://seerr:5055", "key": s["SEERR_KEY"]}
        watch.append({"Request something": tile})
    if watch:
        groups.append({"Watch": watch})

    if "downloads" in ctx.apps:
        groups.append({"Downloads": [
            {"TV shows": {"icon": "sonarr.png", "href": f"http://{host}:8989", "description": "Sonarr",
                          "widget": {"type": "sonarr", "url": "http://sonarr:8989", "key": s["SONARR_KEY"]}}},
            {"Movies": {"icon": "radarr.png", "href": f"http://{host}:7878", "description": "Radarr",
                        "widget": {"type": "radarr", "url": "http://radarr:7878", "key": s["RADARR_KEY"]}}},
            {"Download sources": {"icon": "prowlarr.png", "href": f"http://{host}:9696", "description": "Prowlarr",
                                  "widget": {"type": "prowlarr", "url": "http://prowlarr:9696", "key": s["PROWLARR_KEY"]}}},
            {"Downloads in progress": {"icon": "qbittorrent.png", "href": f"http://{host}:8080", "description": "qBittorrent",
                                       "widget": {"type": "qbittorrent", "url": "http://qbittorrent:8080",
                                                  "username": "admin", "password": s["QBIT_PASSWORD"]}}},
        ]})

    server = [{"Server settings": {"icon": "cockpit.png", "href": f"http://{host}:9090",
                                   "description": "Updates, disks, restart and shut down"}}]
    if "files" in ctx.apps:
        server.append({"Shared folder": {"icon": "samba.png", "description":
                                         f"On Windows, open File Explorer and type \\\\{ctx.host.split('.')[0]}\\Media"}})
    if ctx.generated_password:
        server.append({"Your app password": {"icon": "mdi-key", "description": ctx.generated_password}})
    groups.append({"Server": server})

    settings = {"title": "Home Server", "theme": "light", "color": "stone", "headerStyle": "clean",
                "target": "_self", "hideVersion": True, "statusStyle": "dot",
                "layout": {"Watch": {"style": "row", "columns": 2}, "Downloads": {"style": "row", "columns": 4},
                           "Server": {"style": "row", "columns": 3}}}
    widgets = [{"greeting": {"text_size": "2xl", "text": "Home Server"}},
               {"resources": {"cpu": True, "memory": True, "disk": "/srv/media"}},
               {"datetime": {"text_size": "xl", "format": {"dateStyle": "long", "timeStyle": "short"}}}]

    # Homepage reads YAML; JSON is valid YAML, so no extra library is needed.
    config = DATA / "homepage"
    files = {"services.yaml": groups, "settings.yaml": settings, "widgets.yaml": widgets,
             "bookmarks.yaml": [], "docker.yaml": {}}
    for name, data in files.items():
        write(config / name, json.dumps(data, indent=2) + "\n", ctx.uid, ctx.gid)


# --- connect -------------------------------------------------------------------------------

def call(method, url, body=None, headers=None, opener=None) -> Any:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", "Accept": "application/json", **(headers or {})})
    with (opener or urllib.request.build_opener()).open(req, timeout=60) as resp:
        raw = resp.read()
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


def connect_downloads(ctx):
    s = ctx.secrets
    wait("http://localhost:8080")
    for name, port, category_field, category, folder in (
            ("sonarr", 8989, "tvCategory", "tv", "/data/TV Shows"),
            ("radarr", 7878, "movieCategory", "movies", "/data/Movies")):
        wait(f"http://localhost:{port}/ping")
        api = arr_api(port, s[name.upper() + "_KEY"])
        if not api("GET", "/downloadclient"):
            schema = next(x for x in api("GET", "/downloadclient/schema") if x["implementation"] == "QBittorrent")
            schema.update(name="qBittorrent", enable=True, priority=1)
            fill(schema, host="qbittorrent", port=8080, username="admin", password=s["QBIT_PASSWORD"],
                 **{category_field: category})
            api("POST", "/downloadclient?forceSave=true", schema)
        if not api("GET", "/rootfolder"):
            api("POST", "/rootfolder", {"path": folder})

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


def connect_jellyfin(ctx):
    base = "http://localhost:8096"
    wait(base + "/health")
    if not call("GET", base + "/System/Info/Public").get("StartupWizardCompleted"):
        lang, country = language()
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
    for name, kind, path in (("Movies", "movies", "/data/Movies"), ("Shows", "tvshows", "/data/TV Shows")):
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
        libraries = call("GET", base + "/settings/jellyfin/library?sync=true", opener=session)
        ids = ",".join(lib["id"] for lib in libraries)
        call("GET", f"{base}/settings/jellyfin/library?enable={ids}", opener=session)

        common = {"hostname": None, "port": None, "apiKey": None, "useSsl": False, "baseUrl": "",
                  "is4k": False, "isDefault": True, "syncEnabled": False, "preventSearch": False,
                  "tagRequests": False, "tags": []}
        for name, port, folder, extra in (
                ("sonarr", 8989, "/data/TV Shows", {"enableSeasonFolders": True, "animeTags": []}),
                ("radarr", 7878, "/data/Movies", {"minimumAvailability": "released"})):
            key = ctx.secrets[name.upper() + "_KEY"]
            profiles = arr_api(port, key)("GET", "/qualityprofile")
            profile = next((p for p in profiles if "1080" in p["name"]), profiles[0])
            call("POST", f"{base}/settings/{name}", {
                **common, **extra, "name": name.capitalize(), "hostname": name, "port": port, "apiKey": key,
                "activeProfileId": profile["id"], "activeProfileName": profile["name"],
                "activeDirectory": folder, "externalUrl": f"http://{ctx.host}:{port}"}, opener=session)
        call("POST", base + "/settings/initialize", opener=session)

    ctx.secrets["SEERR_KEY"] = call("GET", base + "/settings/main", opener=session)["apiKey"]
    ctx.save_secrets()


def connect(ctx):
    if "downloads" in ctx.apps:
        connect_downloads(ctx)
    if "jellyfin" in ctx.apps:
        connect_jellyfin(ctx)
    if "requests" in ctx.apps:
        connect_seerr(ctx)
    write_homepage(ctx)


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else ""
    if step not in ("prepare", "connect"):
        sys.exit("usage: setup.py prepare|connect")
    context = Context()
    prepare(context) if step == "prepare" else connect(context)
