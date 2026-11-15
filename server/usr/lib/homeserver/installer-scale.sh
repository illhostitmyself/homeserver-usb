#!/bin/bash
# Starts the installer scaled to the screen: 1x at 768 lines, 1.5x at 1080, 2x at 1440 and up.
# Bigger text is easier to read, and Calamares' built-in map is a fixed small image otherwise.
height=$(head -qn1 /sys/class/drm/card*-*/modes 2>/dev/null | cut -dx -f2 | sort -n | tail -1)
scale=$(awk -v h="${height:-768}" 'BEGIN { s = int(h / 720 * 4) / 4; if (s < 1) s = 1; if (s > 2) s = 2; print s }')
export QT_SCALE_FACTOR=$scale
exec /usr/bin/calamares "$@"
