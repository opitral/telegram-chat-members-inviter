#!/bin/bash

VENV_PATH="./venv/bin/activate"
SCRIPT_PATH="./telegram_chat_members_inviter_cli_client.py"

MAX_DELAY=$((8 * 60 * 60))
RANDOM_DELAY=$((RANDOM % MAX_DELAY))

echo "Delay: $((RANDOM_DELAY / 3600))h $(((RANDOM_DELAY % 3600) / 60))m $((RANDOM_DELAY % 60))s"
sleep $RANDOM_DELAY

# shellcheck disable=SC1090
source $VENV_PATH
python3 $SCRIPT_PATH
