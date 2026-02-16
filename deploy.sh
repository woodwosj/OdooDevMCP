#!/bin/bash
# Deployment script for Odoo Dev MCP Module to VPS
# Target: 155.138.201.83
# Usage: ./deploy.sh

set -e  # Exit on error

# Configuration
VPS_HOST="155.138.201.83"
VPS_USER="root"
SSH_KEY="$HOME/.ssh/odoo_vps"
MODULE_NAME="odoo_dev_mcp"
ODOO_USER="odoo"
ODOO_GROUP="odoo"
CUSTOM_ADDONS="/opt/odoo/custom-addons"
ODOO_VENV="/opt/odoo/odoo-venv"
MODULE_PATH="$CUSTOM_ADDONS/$MODULE_NAME"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Odoo Dev MCP Deployment Script ===${NC}"
echo "Target VPS: $VPS_HOST"
echo "Module: $MODULE_NAME"
echo ""

# Check if SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}ERROR: SSH key not found at $SSH_KEY${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: Testing SSH connection...${NC}"
if ssh -i "$SSH_KEY" -o ConnectTimeout=10 "$VPS_USER@$VPS_HOST" "echo 'SSH connection successful'" 2>/dev/null; then
    echo -e "${GREEN}✓ SSH connection verified${NC}"
else
    echo -e "${RED}ERROR: Cannot connect to VPS${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 2: Creating temporary archive...${NC}"
TEMP_DIR=$(mktemp -d)
ARCHIVE_NAME="$MODULE_NAME.tar.gz"
tar -czf "$TEMP_DIR/$ARCHIVE_NAME" \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='*.log' \
    --exclude='.pytest_cache' \
    --exclude='deploy.sh' \
    -C "$(dirname "$(pwd)")" "$(basename "$(pwd)")"
echo -e "${GREEN}✓ Archive created: $TEMP_DIR/$ARCHIVE_NAME${NC}"

echo -e "${YELLOW}Step 3: Uploading module to VPS...${NC}"
scp -i "$SSH_KEY" "$TEMP_DIR/$ARCHIVE_NAME" "$VPS_USER@$VPS_HOST:/tmp/"
echo -e "${GREEN}✓ Module uploaded${NC}"

echo -e "${YELLOW}Step 4: Installing Python dependencies...${NC}"
ssh -i "$SSH_KEY" "$VPS_USER@$VPS_HOST" << 'ENDSSH'
set -e
echo "Installing Python dependencies into Odoo venv..."
/opt/odoo/odoo-venv/bin/pip install mcp>=1.0.0 pyyaml pydantic requests psycopg2-binary --quiet
echo "✓ Dependencies installed"
ENDSSH
echo -e "${GREEN}✓ Python dependencies installed${NC}"

echo -e "${YELLOW}Step 5: Deploying module files...${NC}"
ssh -i "$SSH_KEY" "$VPS_USER@$VPS_HOST" << ENDSSH
set -e

# Backup existing module if it exists
if [ -d "$MODULE_PATH" ]; then
    echo "Backing up existing module..."
    BACKUP_PATH="${MODULE_PATH}.backup.\$(date +%Y%m%d_%H%M%S)"
    mv "$MODULE_PATH" "\$BACKUP_PATH"
    echo "✓ Backup created: \$BACKUP_PATH"
fi

# Extract new module
echo "Extracting module to $CUSTOM_ADDONS..."
cd "$CUSTOM_ADDONS"
tar -xzf /tmp/$ARCHIVE_NAME
# Rename extracted directory to module name (handles OdooDevMCP -> odoo_dev_mcp)
EXTRACTED_DIR=\$(ls -d */ | grep -iv __pycache__ | head -1 | tr -d '/')
if [ "\$EXTRACTED_DIR" != "$MODULE_NAME" ] && [ -d "\$EXTRACTED_DIR" ]; then
    mv "\$EXTRACTED_DIR" "$MODULE_NAME"
fi

# Set correct ownership
echo "Setting ownership to $ODOO_USER:$ODOO_GROUP..."
chown -R $ODOO_USER:$ODOO_GROUP "$MODULE_PATH"

# Set correct permissions
echo "Setting permissions..."
find "$MODULE_PATH" -type f -exec chmod 644 {} \;
find "$MODULE_PATH" -type d -exec chmod 755 {} \;

# Clean up
rm /tmp/$ARCHIVE_NAME

echo "✓ Module deployed to $MODULE_PATH"
ENDSSH
echo -e "${GREEN}✓ Module files deployed${NC}"

echo -e "${YELLOW}Step 6: Restarting Odoo service...${NC}"
ssh -i "$SSH_KEY" "$VPS_USER@$VPS_HOST" << 'ENDSSH'
set -e
echo "Stopping Odoo service..."
systemctl stop odoo

echo "Waiting 3 seconds..."
sleep 3

echo "Starting Odoo service..."
systemctl start odoo

echo "Waiting for Odoo to start (10 seconds)..."
sleep 10

echo "Checking Odoo service status..."
systemctl status odoo --no-pager || true

echo "✓ Odoo service restarted"
ENDSSH
echo -e "${GREEN}✓ Odoo service restarted${NC}"

echo -e "${YELLOW}Step 7: Verifying deployment...${NC}"

# Check if module directory exists
ssh -i "$SSH_KEY" "$VPS_USER@$VPS_HOST" << ENDSSH
set -e
if [ -d "$MODULE_PATH" ]; then
    echo "✓ Module directory exists: $MODULE_PATH"
    echo "  Files:"
    ls -lh "$MODULE_PATH" | head -n 10
else
    echo "✗ ERROR: Module directory not found"
    exit 1
fi
ENDSSH

# Clean up local temp files
rm -rf "$TEMP_DIR"

echo ""
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "Next steps:"
echo "1. Log into Odoo at: http://$VPS_HOST:8069"
echo "2. Go to Apps > Update Apps List"
echo "3. Search for 'Odoo Dev MCP Server'"
echo "4. Install or upgrade the module"
echo "5. Configure settings in Settings > MCP Server"
echo "6. Create API key in Settings > Users > API Keys"
echo "7. Test health endpoint: curl http://$VPS_HOST:8069/mcp/v1/health"
echo ""
echo "To upgrade the module via command line:"
echo "  ssh -i $SSH_KEY $VPS_USER@$VPS_HOST"
echo "  su - odoo -s /bin/bash"
echo "  /opt/odoo/odoo-venv/bin/python /opt/odoo/odoo-bin -c /etc/odoo.conf -d Loomworks -u $MODULE_NAME --stop-after-init"
echo ""
