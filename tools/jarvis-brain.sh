#!/bin/bash
# jarvis-brain.sh — يشغّل عقل الوكيل مخفياً على Linux/Mac.
cd "$(dirname "$0")/.." || exit 1
exec python3 -m agent_os.hermes_server
