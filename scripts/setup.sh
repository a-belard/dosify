#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="${SCRIPT_DIR}/.."
ENV_FILE="${PKG}/.env"

source /opt/ros/noetic/setup.bash

echo "[dosify] Installing Python dependencies..."
pip3 install -r "${PKG}/requirements.txt" --user --quiet

if [ ! -f "${ENV_FILE}" ]; then
  cp "${PKG}/.env.example" "${ENV_FILE}"
  echo "[dosify] Created ${ENV_FILE} — add your OPENAI_API_KEY before running the demo."
else
  echo "[dosify] Using existing ${ENV_FILE}"
fi

mkdir -p "${PKG}/ocr/scans"

if [ ! -d "${HOME}/catkin_ws/src/dosify" ]; then
  echo "[dosify] ERROR: expected package at ~/catkin_ws/src/dosify"
  exit 1
fi

echo "[dosify] Building catkin package..."
cd "${HOME}/catkin_ws"
catkin build dosify --no-deps
# shellcheck disable=SC1091
source devel/setup.bash

chmod +x "${PKG}/scripts/"*.py "${PKG}/scripts/"*.sh 2>/dev/null || true

echo "[dosify] Setup complete."
echo "  Run demo:  ~/catkin_ws/src/dosify/scripts/dosify.sh --demo"
echo "  Rebuild:   ~/catkin_ws/src/dosify/scripts/refresh_pkg.sh"
