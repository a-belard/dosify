#!/usr/bin/env bash
set -euo pipefail

cd ~/catkin_ws
source /opt/ros/noetic/setup.bash
catkin build dosify --no-deps
# shellcheck disable=SC1091
source devel/setup.bash
echo "dosify refreshed."
