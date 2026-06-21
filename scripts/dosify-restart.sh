#!/usr/bin/env bash
set -euo pipefail
sudo systemctl restart dosify.service
sudo systemctl status dosify.service --no-pager || true
