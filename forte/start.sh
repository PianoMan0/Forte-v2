#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

python -m venv .venv
source .venv/Scripts/activate
pip install --upgrade pip
pip install -r requirements.txt

# Copy example config if needed
if [ ! -f config.json ]; then
  cp config.example.json config.json
fi

echo "Starting Forte..."
python -m forte.app


