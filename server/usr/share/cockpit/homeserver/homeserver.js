// The "Home Server apps" page in Cockpit: shows whether a newer app catalog is out and installs it
// with /usr/lib/homeserver/catalog.sh, which checks the catalog's signature first.
const status = document.getElementById("status");
const button = document.getElementById("update");
const log = document.getElementById("log");
const catalog = "/usr/lib/homeserver/catalog.sh";

function check() {
  status.textContent = "Checking for updates...";
  cockpit.spawn([catalog, "status"], { err: "message" })
    .then(out => {
      const s = JSON.parse(out);
      if (s.latest === null) {
        status.textContent = `App catalog version ${s.installed ?? "unknown"}. Couldn't check for a newer one (no internet?).`;
        button.hidden = true;
      } else if (s.installed === null || s.latest > s.installed) {
        status.textContent = `An update is available: app catalog version ${s.latest} (you have ${s.installed ?? "none"}).`;
        button.hidden = false;
      } else {
        status.textContent = `Your apps are up to date (app catalog version ${s.installed}).`;
        button.hidden = true;
      }
    })
    .catch(e => { status.textContent = `Couldn't check for updates: ${e.message}`; });
}

button.addEventListener("click", () => {
  button.disabled = true;
  log.hidden = false;
  log.textContent = "";
  status.textContent = "Updating. This can take a while; the apps restart on their own.";
  // A sudo rule (/etc/sudoers.d/homeserver-catalog) allows exactly this, so it works without
  // turning on administrative access.
  cockpit.spawn(["sudo", "-n", catalog, "update"], { err: "out" })
    .stream(data => { log.textContent += data; log.scrollTop = log.scrollHeight; })
    .then(() => { button.disabled = false; check(); })
    .catch(e => {
      button.disabled = false;
      status.textContent = "The update didn't finish. Your apps are back on the version they had.";
    });
});

check();
