#!/bin/bash
set -u
REPOS=(
  "D4Vinci/Scrapling"
  "OpenBMB/EdgeClaw"
  "OpenBMB/ClawXRouter"
  "privacyshield-ai/privacy-firewall"
  "tinyhumansai/openhuman"
  "garrytan/gbrain"
  "affaan-m/ECC"
  "massgen/MassGen"
  "safishamsi/graphify"
  "jlevere/obsidian-mcp-plugin"
  "bitbonsai/mcpvault"
)
for r in "${REPOS[@]}"; do
  slug="${r//\//__}"
  if [ -d "repos-audit/$slug/.git" ]; then
    echo "EXISTS $slug"; continue
  fi
  echo "CLONE  $r -> repos-audit/$slug"
  git clone --depth 1 "https://github.com/$r" "repos-audit/$slug" 2>&1 | tail -2
done
echo "---"
du -sh repos-audit/* 2>/dev/null | sort
