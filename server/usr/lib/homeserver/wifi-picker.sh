#!/bin/bash
# The Wi-Fi screen (runs inside foot). nmtui lists the networks; it's closed as soon as one connects.
connected() { ip route show default | grep -q . || ip -6 route show default | grep -q .; }
network() { nmcli -t -f TYPE,CONNECTION device | sed -n 's/^wifi://p' | head -1; }

while true; do
  clear
  cat <<'EOF'

  No network cable found, so let's connect to Wi-Fi.

  On the next screen, use the arrow keys to pick your network and press Enter,
  then type the Wi-Fi password and press Enter.

  Press Enter to see the Wi-Fi networks.
EOF
  read -r

  ( until connected; do sleep 1; done; pkill -x nmtui ) &
  watcher=$!
  nmtui connect
  kill "$watcher" 2>/dev/null
  stty sane
  clear

  if connected; then
    printf '\n  Connected to %s. Starting the installer...\n' "$(network)"
    sleep 2
    exit 0
  fi
  cat <<'EOF'

  Not connected.

  Press Enter to try again, or type S and press Enter to install without internet.
  Without internet the apps are set up the first time the server is online.
EOF
  read -r answer
  [[ ${answer,,} == s* ]] && exit 0
done
