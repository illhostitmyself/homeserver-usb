// The "Home Server apps" page in Cockpit. Updates: shows whether a newer app catalog is out and
// installs it. Your apps: adds and removes apps. Both go through /usr/lib/homeserver/catalog.sh,
// which only uses catalog releases signed with the Home Server key.
const status = document.getElementById("status");
const updateButton = document.getElementById("update");
const updateBox = document.getElementById("update-box");
const updatePassword = document.getElementById("update-password");
const updateError = document.getElementById("update-error");
const log = document.getElementById("log");
const appsBox = document.getElementById("apps");
const change = document.getElementById("change");
const planText = document.getElementById("plan");
const password = document.getElementById("password");
const applyButton = document.getElementById("apply");
const error = document.getElementById("error");
const done = document.getElementById("done");
const catalog = "/usr/lib/homeserver/catalog.sh";
const appsPy = "/var/lib/homeserver/catalog/apps.py";

let store = null;      // apps.py store: groups, apps, installed
let wanted = new Set(); // what the owner ticked
let busy = false;

function setBusy(on) {
  busy = on;
  updateButton.disabled = on;
  applyButton.disabled = on;
  appsBox.querySelectorAll("input").forEach(box => { box.disabled = on || box.dataset.locked === "1"; });
}

function showLog() {
  log.hidden = false;
  log.textContent = "";
}

function append(data) {
  log.textContent += data;
  log.scrollTop = log.scrollHeight;
}

function check() {
  status.textContent = "Checking for updates...";
  cockpit.spawn([catalog, "status"], { err: "message" })
    .then(out => {
      const s = JSON.parse(out);
      if (s.latest === null) {
        status.textContent = `App catalog version ${s.installed ?? "unknown"}. Couldn't check for a newer one (no internet?).`;
        updateBox.hidden = true;
      } else if (s.installed === null || s.latest > s.installed) {
        status.textContent = `An update is available: app catalog version ${s.latest} (you have ${s.installed ?? "none"}).`;
        updateBox.hidden = false;
      } else {
        status.textContent = `Your apps are up to date (app catalog version ${s.installed}).`;
        updateBox.hidden = true;
      }
    })
    .catch(e => { status.textContent = `Couldn't check for updates: ${e.message}`; });
}

// The password is checked against the owner's account, then handed to the update so it can apply the
// apps' logins and links again.
function checkPassword(value) {
  return cockpit.spawn(["/usr/bin/sudo", "-S", "-k", "-v", "-p", ""], { err: "message" }).input(value + "\n");
}

updateButton.addEventListener("click", () => {
  updateError.hidden = true;
  if (!updatePassword.value) {
    updateError.textContent = "Type your password first.";
    updateError.hidden = false;
    return;
  }
  setBusy(true);
  checkPassword(updatePassword.value).then(() => {
    showLog();
    status.textContent = "Updating. This can take a while; the apps restart on their own.";
    // A sudo rule (/etc/sudoers.d/homeserver-catalog) allows exactly this, so it works without
    // turning on administrative access.
    return cockpit.spawn(["/usr/bin/sudo", "-n", catalog, "update"], { err: "out" })
      .input(updatePassword.value + "\n")
      .stream(append)
      .then(() => { updatePassword.value = ""; setBusy(false); check(); loadApps(); })
      .catch(() => {
        setBusy(false);
        status.textContent = "The update didn't finish. Your apps are back on the version they had.";
      });
  }, () => {
    setBusy(false);
    updateError.textContent = "That password isn't right.";
    updateError.hidden = false;
  });
});

function loadApps() {
  cockpit.spawn(["/usr/bin/python3", appsPy, "store"], { err: "message" })
    .then(out => {
      store = JSON.parse(out);
      wanted = new Set(store.installed);
      draw();
      return replan();
    })
    .catch(() => {
      appsBox.innerHTML = "<p>Adding and removing apps needs a newer app catalog. Update the apps above first.</p>";
    });
}

function draw() {
  appsBox.textContent = "";
  for (const group of store.groups) {
    const h = document.createElement("h3");
    h.textContent = group.name;
    const hint = document.createElement("p");
    hint.className = "hint";
    hint.textContent = group.description;
    appsBox.append(h, hint);
    for (const app of group.apps) {
      const row = document.createElement("label");
      row.className = "app";
      row.dataset.app = app.id;
      const box = document.createElement("input");
      box.type = "checkbox";
      box.dataset.app = app.id;
      const text = document.createElement("div");
      const name = document.createElement("div");
      name.className = "name";
      name.textContent = app.name;
      const desc = document.createElement("div");
      desc.className = "desc";
      desc.textContent = app.description + (app.cost?.[0] ? ` · ${size(app.cost[0])} download` : "");
      const note = document.createElement("div");
      note.className = "note";
      text.append(name, desc, note);
      row.append(box, text);
      appsBox.append(row);
      box.addEventListener("change", () => {
        box.checked ? wanted.add(app.id) : wanted.delete(app.id);
        replan();
      });
    }
  }
}

function size(mb) {
  return mb >= 1000 ? `${(mb / 1000).toFixed(1)} GB` : `${mb} MB`;
}

function names(ids) {
  const all = Object.fromEntries(store.groups.flatMap(g => g.apps).map(a => [a.id, a.name]));
  return ids.map(id => all[id]).join(", ");
}

let planned = null;
function replan() {
  return cockpit.spawn(["/usr/bin/python3", appsPy, "plan", ...wanted], { err: "message" })
    .then(out => {
      planned = JSON.parse(out);
      const apps = new Set(planned.apps);
      for (const row of appsBox.querySelectorAll(".app")) {
        const id = row.dataset.app;
        const box = row.querySelector("input");
        const info = store.groups.flatMap(g => g.apps).find(a => a.id === id);
        const installed = store.installed.includes(id) || Boolean(info.system);
        const on = info.always || apps.has(id);
        box.checked = on;
        // Always-installed apps, and apps another ticked app needs, can't be unticked.
        const locked = info.always || (id in planned.needed);
        box.dataset.locked = locked ? "1" : "0";
        box.disabled = busy || locked;
        row.querySelector(".note").textContent = info.always ? "Always installed"
          : id in planned.needed ? `Needed by ${planned.needed[id].join(", ")}` : "";
        row.classList.toggle("adding", on && !installed);
        row.classList.toggle("removing", !on && installed);
      }
      const parts = [];
      if (planned.add.length) {
        const mb = planned.add.reduce((sum, id) => {
          const app = store.groups.flatMap(g => g.apps).find(a => a.id === id);
          return sum + (app.cost ? app.cost[0] : 0);
        }, 0);
        parts.push(`Adds ${names(planned.add)} (about ${size(mb)} to download).`);
      }
      if (planned.remove.length) parts.push(`Removes ${names(planned.remove)}.`);
      planText.textContent = parts.join(" ");
      change.hidden = parts.length === 0;
    });
}

applyButton.addEventListener("click", () => {
  error.hidden = true;
  done.hidden = true;
  if (!password.value) {
    error.textContent = "Type your password first.";
    error.hidden = false;
    return;
  }
  setBusy(true);
  // The new apps get this password, so check it's really the owner's before using it.
  checkPassword(password.value)
    .then(() => {
      showLog();
      planText.textContent = "Changing your apps. This can take a while...";
      return cockpit.spawn(["/usr/bin/sudo", "-n", catalog, "apps"], { err: "out" })
        .input(password.value + "\n" + [...wanted].join(" ") + "\n")
        .stream(append)
        .then(() => {
          password.value = "";
          done.textContent = "Done. Your apps are on the dashboard.";
          done.hidden = false;
          setBusy(false);
          loadApps();
        })
        .catch(() => {
          setBusy(false);
          error.textContent = "That didn't finish. The details are below; Apply changes tries again.";
          error.hidden = false;
        });
    }, () => {
      setBusy(false);
      error.textContent = "That password isn't right.";
      error.hidden = false;
    });
});

// Dashboard look: the choices live in /etc/homeserver/dashboard.json (readable by everyone); saving goes
// through catalog.sh look, which writes the Homepage settings.
const COLORS = ["slate", "gray", "zinc", "neutral", "stone", "red", "orange", "amber", "yellow", "lime", "green",
  "emerald", "teal", "cyan", "sky", "blue", "indigo", "violet", "purple", "fuchsia", "pink", "rose"];
const lookTitle = document.getElementById("look-title");
const lookTheme = document.getElementById("look-theme");
const lookColor = document.getElementById("look-color");
const lookPicture = document.getElementById("look-picture");
const lookRemove = document.getElementById("look-remove");
const lookStatus = document.getElementById("look-status");
for (const c of COLORS) lookColor.append(new Option(c[0].toUpperCase() + c.slice(1), c));

function loadLook() {
  cockpit.file("/etc/homeserver/dashboard.json", { syntax: JSON }).read()
    .then(saved => {
      const look = { title: "Home Server", theme: "light", color: "stone", background: "", ...(saved || {}) };
      lookTitle.value = look.title;
      lookTheme.value = look.theme;
      lookColor.value = look.color;
      document.getElementById("look-remove-row").hidden = !look.background;
      lookRemove.checked = false;
    })
    .catch(() => {});
}

function pictureData(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(",", 2)[1]);
    reader.onerror = () => reject(new Error("That picture couldn't be read"));
    reader.readAsDataURL(file);
  });
}

document.getElementById("look-save").addEventListener("click", async () => {
  const save = document.getElementById("look-save");
  save.disabled = true;
  lookStatus.hidden = false;
  lookStatus.className = "status";
  lookStatus.textContent = "Saving...";
  try {
    let background = lookRemove.checked ? "remove" : "keep";
    if (lookPicture.files.length) background = await pictureData(lookPicture.files[0]);
    const out = await cockpit.spawn(["/usr/bin/sudo", "-n", catalog, "look"], { err: "message" })
      .input(JSON.stringify({ title: lookTitle.value, theme: lookTheme.value, color: lookColor.value, background }));
    lookStatus.textContent = out.trim() || "Saved.";
    lookPicture.value = "";
    loadLook();
  } catch (e) {
    lookStatus.className = "error";
    lookStatus.textContent = e.message || String(e);
  }
  save.disabled = false;
});

check();
loadApps();
loadLook();
