# Contributing

Thanks for helping. Home Server is built for people who have never run a server: everything they
see has to work without a terminal, and every word on screen has to make sense to someone who
doesn't know what Docker is. Keep that in mind for any change.

## Reporting a problem

Open an issue with:

- What you did, what you expected, and what happened instead. A photo of the screen is fine.
- The app catalog version (the Apps page shows it) and, for install problems, the ISO version.
- The computer: brand and model, or at least CPU, memory, disks and how it connects to the network.
- Logs, if you can get them: the log box on the Apps page after an update or app change,
  `journalctl -u 'homeserver*'` on the server, and `/var/log/homeserver-update.log` after updating
  from a USB stick.

**Before posting, remove anything personal from logs and screenshots:** your name, passwords, API
keys, addresses, Tailscale names, and the titles of what's in your library.

Security problems don't go in issues; see [SECURITY.md](SECURITY.md).

## Suggesting an app or a feature

Open an issue first and describe who it's for and what it replaces, before writing code. An app
belongs in the catalog when it fits the rest (self-hosted, has an official image with versioned
tags, works with the shared `/data` layout) and can be set up completely without the owner opening
its settings.

## How the repository is laid out

| Folder | What's in it |
|---|---|
| `catalog/` | The app catalog: every app's Compose service, the setup that configures and connects them, and the scripts servers run to update. See [catalog/README.md](catalog/README.md) |
| `server/` | Files installed on every server: services, the Cockpit page, the kiosk, the update scripts. Servers also get these from catalog releases |
| `installer/` | The Calamares installer: its settings, pages and Python modules |
| `live/` | The live-build configuration for the ISO |
| `builder/`, `build.sh` | Builds the ISO in Docker |
| `test/` | `vm.sh` boots the ISO or an installed system in QEMU, `qmp.py` takes screenshots and types into it |
| `docs/` | The install guide and its screenshots |

## Making a change

1. Fork the repository and make a branch from `main`.
2. Make one change per pull request. A bug fix and a new feature are two pull requests.
3. Test it (see below) and say in the pull request exactly how.
4. Open a pull request against `main`.

`main` is protected: every change goes through a pull request, needs one approving review, has
every review conversation resolved, and is squash-merged. A push to the branch after an approval
needs a new approval.

### Testing

You need Docker, QEMU with KVM, and about 15 GB of free disk.

```bash
./build.sh              # builds out/homeserver-usb.iso
test/vm.sh --reset      # installs it in a VM, as if from a USB stick
test/vm.sh --disk       # starts the installed VM
test/vm.sh --window     # the same, in a window you can click through
```

Changes to the installer or the ISO need a fresh install in the VM. Changes to `catalog/` or
`server/` should also be tested as an update to a server installed from the current release, since
that's how existing servers get them.

Catalog releases are signed with a key only the maintainer has, and servers refuse anything else.
To test catalog changes on your own VM, make your own key with
`ssh-keygen -t ed25519 -f ~/catalog-test-key`, add its public half to
`server/usr/share/homeserver/catalog-signers` **in your local build only**, sign with it, and serve
the catalog over HTTP (see "Build it yourself" in the README). Never commit a key or a change to
`catalog-signers`.

### What a pull request must not include

- A change to `"version"` in `catalog/catalog.json`, release files, or anything signed. Versions are
  raised when the maintainer releases.
- A change to `catalog-signers`, or any key, token or password, even a test one.
- An image without a pinned tag and `@sha256:` digest, or one that isn't from the app's publisher.
- Screenshots or logs with personal information in them.

### Style

- Shell scripts are Bash with `set -euo pipefail` (or `-uo` where a failure is handled). Python is
  for logic that talks to app APIs; it never runs other programs (no `subprocess`). Anything that
  needs to run a program stays in Bash.
- Match the code around your change: names, comment density, error messages. Comment why, not
  what.
- Everything setup does has to be safe to run again: updates run it on every server, every time.
  Never overwrite something the owner may have changed in an app; add what's missing and leave the
  rest.
- Text the owner sees is short, plain and specific: "Couldn't download the apps (no internet?)", not
  "Error: pull failed".

## License

By contributing you agree that your work is released under the [MIT License](LICENSE).
