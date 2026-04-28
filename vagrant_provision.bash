#!/usr/bin/env bash
#
# Full provisioning workflow for Windows development VM
# Handles automatic reloads and credential switching
#
# Usage: ./vagrant_provision.bash
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CREDS_DIR="${SCRIPT_DIR}/.credentials"
ADMIN_READY_FLAG="${SCRIPT_DIR}/synced/admin-ready"
TRANSITION_FLAG="${SCRIPT_DIR}/.vagrant/admin-transitioned"
ENV_FILE="${SCRIPT_DIR}/.env"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() {
	echo -e "${BLUE}[INFO]${NC} $*"
}

success() {
	echo -e "${GREEN}[SUCCESS]${NC} $*"
}

warning() {
	echo -e "${YELLOW}[WARNING]${NC} $*"
}

# Load environment variables from .env file
if [[ ! -f "${ENV_FILE}" ]]; then
	echo "ERROR: .env file not found at: ${ENV_FILE}"
	echo "Please create a .env file with GITHUB_TOKEN=<your-token>"
	echo "-- have gh? --> echo \"GITHUB_TOKEN=\$(gh auth token)\" > .env"
	exit 1
fi

info "Loading environment variables from .env..."
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

# Generate credentials if they don't exist
ADMIN_PASSWORD_FILE="${CREDS_DIR}/admin.txt"
USER_PASSWORD_FILE="${CREDS_DIR}/user.txt"

if [[ ! -f "${ADMIN_PASSWORD_FILE}" ]] || [[ ! -f "${USER_PASSWORD_FILE}" ]]; then
	info "Credentials not found, generating new passwords..."
	mkdir -p "${CREDS_DIR}"

	if [[ ! -f "${ADMIN_PASSWORD_FILE}" ]]; then
		info "Generating admin password..."
		openssl rand -base64 32 | tr -dc 'A-HJ-NP-Za-hj-np-z2-9' | head -c 19 | tr -d '\n' >"${ADMIN_PASSWORD_FILE}"
		echo -n '_' >>"${ADMIN_PASSWORD_FILE}"
		chmod 600 "${ADMIN_PASSWORD_FILE}"
		success "Admin password generated"
	fi

	if [[ ! -f "${USER_PASSWORD_FILE}" ]]; then
		info "Generating user password..."
		openssl rand -base64 32 | tr -dc 'A-HJ-NP-Za-hj-np-z2-9' | head -c 19 | tr -d '\n' >"${USER_PASSWORD_FILE}"
		echo -n '_' >>"${USER_PASSWORD_FILE}"
		chmod 600 "${USER_PASSWORD_FILE}"
		success "User password generated"
	fi

	success "Credentials saved to: ${CREDS_DIR}/"
	echo ""
else
	info "Using existing credentials from: ${CREDS_DIR}/"
fi

# Export credentials
ADMIN_PASSWORD="$(cat "${ADMIN_PASSWORD_FILE}")"
export ADMIN_PASSWORD
USER_PASSWORD="$(cat "${USER_PASSWORD_FILE}")"
export USER_PASSWORD

# Unpack appearance export if not already present
APPEARANCE_DIR="${SCRIPT_DIR}/synced/Win11AppearanceExport"
APPEARANCE_ARCHIVE="${SCRIPT_DIR}/Win11AppearanceExport.tar.gz"

if [[ ! -d "${APPEARANCE_DIR}" ]]; then
	if [[ -f "${APPEARANCE_ARCHIVE}" ]]; then
		info "Unpacking Win11AppearanceExport into synced/..."
		tar xzf "${APPEARANCE_ARCHIVE}" -C "${SCRIPT_DIR}/synced/"
		success "Appearance export unpacked to: ${APPEARANCE_DIR}"
	else
		warning "No Win11AppearanceExport.tar.gz found - skipping appearance restore data"
	fi
else
	info "Appearance export already present at: ${APPEARANCE_DIR}"
fi
echo ""

info "Starting full provisioning workflow..."
echo ""

# Check and install required Vagrant plugins
info "Checking for required Vagrant plugins..."
if ! vagrant plugin list | grep -q 'vagrant-vbguest'; then
	info "Installing vagrant-vbguest plugin..."
	vagrant plugin install vagrant-vbguest
	success "Plugin installed"
else
	info "vagrant-vbguest plugin already installed"
fi
echo ""

# Phase 1: Initial provisioning as vagrant user
info "Phase 1: Setting up hardware and creating user accounts (running as vagrant user)..."
info "Note: VM will reload inbetween to update PATH and users"
vagrant up

# Wait for admin-ready flag
info "Waiting for admin user to be ready..."
WAIT_COUNT=0
MAX_WAIT=60 # 60 seconds max wait

while [[ ! -f "${ADMIN_READY_FLAG}" ]] && [[ ${WAIT_COUNT} -lt ${MAX_WAIT} ]]; do
	sleep 1
	((WAIT_COUNT++))
done

if [[ ! -f "${ADMIN_READY_FLAG}" ]]; then
	echo "ERROR: Admin ready flag not found after ${MAX_WAIT} seconds"
	echo "Expected flag at: ${ADMIN_READY_FLAG}"
	echo "Phase 1 may have failed. Check 'vagrant up' output above."
	exit 1
fi

success "Admin user is ready!"
echo ""

# Mark transition
mkdir -p "$(dirname "${TRANSITION_FLAG}")"
touch "${TRANSITION_FLAG}"

# Phase 2: Reload with admin credentials and finalize
info "Phase 2: Reloading VM to switch to admin credentials and finalize setup..."
vagrant reload --provision

success "Finalization complete!"
echo ""

# Final reload to activate autologon
info "Final reload to activate autologon..."
vagrant reload

success "Provisioning complete!"
echo ""
info "The VM is now configured with:"
info "  - Admin user: admin"
info "  - Unprivileged user: user"
info "  - Autologon configured for: user"
info ""
info "Credentials are stored in: ${CREDS_DIR}/"
info ""
info "Next steps:"
info "  1. View the VM GUI - it should be logged in to 'user'"
info "  2. You should see a welcome popup on first login"
echo ""
