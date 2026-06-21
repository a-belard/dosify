#!/usr/bin/env bash
set -euo pipefail

UNIT_NAME="dosify.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_SRC="${SCRIPT_DIR}/../systemd/${UNIT_NAME}"
SYSTEM_UNIT="/etc/systemd/system/${UNIT_NAME}"

chmod +x "${SCRIPT_DIR}/dosify-autostart.sh"
chmod +x "${SCRIPT_DIR}/dosify-restart.sh"
chmod +x "${SCRIPT_DIR}/dosify.sh"
chmod +x "${SCRIPT_DIR}/setup.sh"
chmod +x "${SCRIPT_DIR}/refresh_pkg.sh"
chmod +x "${SCRIPT_DIR}"/*.py

sudo cp "${UNIT_SRC}" "${SYSTEM_UNIT}"
sudo systemctl daemon-reload
sudo systemctl enable "${UNIT_NAME}"
sudo systemctl restart "${UNIT_NAME}"

echo ""
echo "Dosify system service installed."
echo "Run demo manually:  dosify.sh --demo"
echo "Restart service:    dosify-restart.sh"
echo "Logs:               sudo journalctl -u dosify -n 50 --no-pager"
sudo systemctl status "${UNIT_NAME}" --no-pager || true
