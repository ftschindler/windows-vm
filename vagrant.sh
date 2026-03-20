#!/usr/bin/env bash
#
# Helper script to run vagrant commands with credentials loaded
# Usage: ./vagrant.sh <vagrant-command> [args...]
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CREDS_DIR="${SCRIPT_DIR}/.credentials"
ENV_FILE="${SCRIPT_DIR}/.env"

# Determine if this command needs credentials
VAGRANT_COMMAND="${1:-}"
NO_CREDS_COMMANDS="destroy|global-status|status|halt|suspend|resume|version|plugin|box"

# Commands that don't need credentials can run directly
if [[ "${VAGRANT_COMMAND}" =~ ^(${NO_CREDS_COMMANDS})$ ]]; then
	# Run directly without credentials
	exec vagrant "$@"
fi

# Load environment variables from .env file
if [[ ! -f "${ENV_FILE}" ]]; then
	echo "ERROR: .env file not found at: ${ENV_FILE}"
	echo "Please create a .env file with GITHUB_TOKEN=<your-token>"
	exit 1
fi

set -a
# shellcheck source=/dev/null
source "${ENV_FILE}"
set +a

# Verify GITHUB_TOKEN is set
if [[ -z "${GITHUB_TOKEN:-}" ]]; then
	echo "ERROR: GITHUB_TOKEN not found in .env file"
	echo "Please add GITHUB_TOKEN=<your-token> to ${ENV_FILE}"
	exit 1
fi

export GITHUB_TOKEN

# Check if credentials exist (for commands that need them)
if [[ ! -f "${CREDS_DIR}/admin.txt" ]] || [[ ! -f "${CREDS_DIR}/user.txt" ]]; then
	echo "ERROR: Credentials not found."
	echo "Please run: bash ./generate-credentials.sh"
	exit 1
fi

# Export credentials
ADMIN_PASSWORD="$(cat "${CREDS_DIR}/admin.txt")"
export ADMIN_PASSWORD
USER_PASSWORD="$(cat "${CREDS_DIR}/user.txt")"
export USER_PASSWORD

# Run vagrant command
exec vagrant "$@"
