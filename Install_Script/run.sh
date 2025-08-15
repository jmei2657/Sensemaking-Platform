#!/usr/bin/env bash
set -e  # Exit on error
set -u  # Treat unset variables as error

# ----------- CONFIGURATION -----------
GIT_REPO_URL="https://github.com/dculverew/EW2025SMP"
GIT_REPO_DIR="EW2025SMP"   
# -------------------------------------

echo "=== Updating system ==="
sudo apt-get update -y
sudo apt-get upgrade -y

echo "=== Installing base packages ==="
# Install all manually recorded packages
# Remove duplicates just in case
sort -u manually_installed.txt > manually_installed_clean.txt
sudo xargs -a manually_installed_clean.txt apt-get install -y

echo "=== Installing additional tools ==="
echo "Adding Microsoft VS Code repository..."
wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > packages.microsoft.gpg
sudo install -o root -g root -m 644 packages.microsoft.gpg /usr/share/keyrings/
sudo sh -c 'echo "deb [arch=amd64 signed-by=/usr/share/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/vscode stable main" > /etc/apt/sources.list.d/vscode.list'
sudo apt-get install -y apt-transport-https
sudo apt-get update
sudo apt-get install -y code

echo "=== Cloning Git repository ==="
if [ -d "$GIT_REPO_DIR" ]; then
    echo "Directory $GIT_REPO_DIR already exists, skipping clone."
else
    git clone "$GIT_REPO_URL"
fi

echo "=== Entering project directory: $GIT_REPO_DIR ==="
cd "$GIT_REPO_DIR"

echo "=== Setting up Python virtual environment ==="
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools

if [ -f requirements.txt ]; then
    echo "Installing Python dependencies..."
    pip install -r requirements.txt
else
    echo "No requirements.txt found, skipping pip install."
fi


echo "=== Done! ==="
