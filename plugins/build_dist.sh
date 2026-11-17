#!/usr/bin/env bash
# Builds the installable files in dist/:
#   dist/marsad-ships.plugin                  -> Claude Cowork (whole plugin)
#   dist/ship-report.zip   -> claude.ai Skills upload (skill only)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
dist="$here/../dist"
mkdir -p "$dist"
rm -f "$dist"/*.plugin "$dist"/*.zip
find "$here/marsad-ships" -name "__pycache__" -type d -prune -exec rm -rf {} +
(cd "$here/marsad-ships" && zip -qr "$dist/marsad-ships.plugin" . -x "*.DS_Store")
(cd "$here/marsad-ships/skills" && zip -qr "$dist/ship-report.zip" ship-report -x "*.DS_Store")
ls -l "$dist"
