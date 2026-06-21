#!/usr/bin/env bash
set -euo pipefail

DEMO=false
EXTRA=()
for arg in "$@"; do
  case "$arg" in
    --demo|-demo) DEMO=true ;;
    *) EXTRA+=("$arg") ;;
  esac
done

source /opt/ros/noetic/setup.bash
if [ -f "${HOME}/catkin_ws/devel/setup.bash" ]; then
  # shellcheck disable=SC1091
  source "${HOME}/catkin_ws/devel/setup.bash"
fi

if [ "${DEMO}" = true ]; then
  exec roslaunch dosify demo.launch "${EXTRA[@]}"
fi

exec roslaunch dosify dosify.launch "${EXTRA[@]}"
