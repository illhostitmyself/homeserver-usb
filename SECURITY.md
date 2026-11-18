# Security

Please don't report security problems in public issues, pull requests or chat.

Report them privately through GitHub: open the repository's **Security** tab and click **Report a
vulnerability**. Include what's affected, how to reproduce it, and what an attacker could do with
it. You'll get an answer there.

## What counts

Anything that lets someone change what servers run, or get into a server or its apps without the
owner's password. For example:

- getting a server to accept an app catalog that isn't signed with the Home Server key, or an older
  one than it has;
- a way around the Cockpit page's sudo rule (`/etc/sudoers.d/homeserver-catalog`);
- passwords or API keys exposed to the network or to other users;
- something the installer or setup does that leaves a server open to the home network in a way the
  README doesn't describe.

The README's [Security notes](README.md#security-notes) describe what's expected: the dashboard has
no login and the apps use plain HTTP inside the home network. That alone isn't a vulnerability.
