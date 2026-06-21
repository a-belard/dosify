#!/usr/bin/env bash
set -eo pipefail

export HOME="${HOME:-/home/niryo}"

log() {
  echo "[dosify-autostart] $*"
}

source_ros() {
  # shellcheck disable=SC1091
  source /opt/ros/noetic/setup.bash
  if [ -f "${HOME}/catkin_ws/devel/setup.bash" ]; then
    # shellcheck disable=SC1091
    source "${HOME}/catkin_ws/devel/setup.bash"
  fi
}

source_ros

CONFIG="${HOME}/catkin_ws/src/dosify/config/robot_config.yaml"
AUTOSTART_DEMO=false
if [ -f "${CONFIG}" ] && grep -q 'autostart_demo:[[:space:]]*true' "${CONFIG}"; then
  AUTOSTART_DEMO=true
fi

wait_for_stack() {
  local i
  for i in $(seq 1 120); do
    if rostopic list &>/dev/null \
        && rosservice list 2>/dev/null | grep -q '/niryo_robot_poses_handlers/get_pose'; then
      log "Niryo ROS stack ready."
      return 0
    fi
    sleep 2
  done
  log "Timed out waiting for Niryo ROS stack."
  return 1
}

log "Waiting for Niryo ROS stack..."
if ! wait_for_stack; then
  exit 1
fi

if [ "${AUTOSTART_DEMO}" = true ]; then
  log "Launching dosify demo..."
  exec roslaunch dosify demo.launch
fi

log "Launching dosify (idle nodes; run dosify.sh --demo manually)..."
exec roslaunch dosify dosify.launch
