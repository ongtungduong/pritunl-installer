#!/bin/bash

CODENAME=$(lsb_release -cs)
PROTOCOL=$( [ $CODENAME = "focal" ] && echo "http" || echo "https" )
REPO="$PROTOCOL://repo.pritunl.com/stable/apt"

# Prompt for installation type
read -p "Enter installation type (server/client) [Default: server]: " TYPE
INSTALLATION_TYPE=${TYPE:-"server"}

# Add Pritunl repository
echo "deb $REPO $CODENAME main" | sudo tee /etc/apt/sources.list.d/pritunl.list
sudo apt --assume-yes install gnupg
gpg --keyserver hkp://keyserver.ubuntu.com --recv-keys 7568D9BB55FF9E5287D586017AE645C0CF8E292A
gpg --armor --export 7568D9BB55FF9E5287D586017AE645C0CF8E292A | sudo tee /etc/apt/trusted.gpg.d/pritunl.asc

if [ "$INSTALLATION_TYPE" = "client" ]; then
    # Install Pritunl Client
    sudo apt update -y
    sudo apt install pritunl-client wireguard wireguard-tools -y
    echo "Pritunl Client installed successfully"
    exit 0
fi

# Add MongoDB repository
sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list << EOF
deb https://repo.mongodb.org/apt/ubuntu $CODENAME/mongodb-org/6.0 multiverse
EOF
wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo apt-key add -

# Install WireGuard, Pritunl Server and MongoDB
sudo apt update -y
sudo apt install wireguard wireguard-tools -y
sudo apt install pritunl mongodb-org -y

# Disable UFW and enable services
sudo ufw disable
sudo systemctl enable mongod pritunl --now
echo "Pritunl Server installed successfully"
