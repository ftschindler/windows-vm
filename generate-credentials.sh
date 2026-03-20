#!/usr/bin/env bash
#
# Generate random passwords for admin and user accounts
#
# Note: vagrant_provision.bash auto-generates credentials if missing.
# This script is only needed for manual workflow or credential regeneration.
#
# Usage: bash ./generate-credentials.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CREDS_DIR="${SCRIPT_DIR}/.credentials"

# Create credentials directory if it doesn't exist
mkdir -p "${CREDS_DIR}"

# Generate admin password if it doesn't exist
ADMIN_PASSWORD_FILE="${CREDS_DIR}/admin.txt"
if [[ ! -f "${ADMIN_PASSWORD_FILE}" ]]; then
	echo "Generating admin password..."
	# Generate 19 random chars + underscore
	openssl rand -base64 32 | tr -dc 'A-HJ-NP-Za-hj-np-z2-9' | head -c 19 | tr -d '\n' >"${ADMIN_PASSWORD_FILE}"
	echo -n '_' >>"${ADMIN_PASSWORD_FILE}"
	chmod 600 "${ADMIN_PASSWORD_FILE}"
	echo "✓ Admin password generated: ${ADMIN_PASSWORD_FILE}"
else
	echo "✓ Admin password already exists: ${ADMIN_PASSWORD_FILE}"
fi

# Generate user password if it doesn't exist
USER_PASSWORD_FILE="${CREDS_DIR}/user.txt"
if [[ ! -f "${USER_PASSWORD_FILE}" ]]; then
	echo "Generating user password..."
	# Generate 19 random chars + underscore
	openssl rand -base64 32 | tr -dc 'A-HJ-NP-Za-hj-np-z2-9' | head -c 19 | tr -d '\n' >"${USER_PASSWORD_FILE}"
	echo -n '_' >>"${USER_PASSWORD_FILE}"
	chmod 600 "${USER_PASSWORD_FILE}"
	echo "✓ User password generated: ${USER_PASSWORD_FILE}"
else
	echo "✓ User password already exists: ${USER_PASSWORD_FILE}"
fi

# Export as environment variables
ADMIN_PASSWORD="$(cat "${ADMIN_PASSWORD_FILE}")"
export ADMIN_PASSWORD
USER_PASSWORD="$(cat "${USER_PASSWORD_FILE}")"
export USER_PASSWORD

echo ""
echo "Credentials stored in:"
echo "  ${ADMIN_PASSWORD_FILE}"
echo "  ${USER_PASSWORD_FILE}"
echo ""
echo "Next steps:"
echo "  - Automated: bash ./vagrant_provision.bash"
echo "  - Manual: ./vagrant.sh up"
