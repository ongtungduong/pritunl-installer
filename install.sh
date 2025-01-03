#!/bin/bash

INSTALLATION_TYPE=${INSTALLATION_TYPE:-"server"}
UBUNTU_CODENAME=$(lsb_release -cs)
REPO_PROTOCOL=$( [ $UBUNTU_CODENAME = "focal" ] && echo "http" || echo "https" )
PRITUNL_REPO="$REPO_PROTOCOL://repo.pritunl.com/stable/apt"

# Add Pritunl repository
echo "deb $PRITUNL_REPO $UBUNTU_CODENAME main" | sudo tee /etc/apt/sources.list.d/pritunl.list
sudo apt --assume-yes install gnupg
gpg --keyserver hkp://keyserver.ubuntu.com --recv-keys 7568D9BB55FF9E5287D586017AE645C0CF8E292A
gpg --armor --export 7568D9BB55FF9E5287D586017AE645C0CF8E292A | sudo tee /etc/apt/trusted.gpg.d/pritunl.asc

if [ "$INSTALLATION_TYPE" = "client" ]; then
    # Install Pritunl Client
    sudo apt update -y
    sudo apt install pritunl-client -y
    exit 0
fi

# Add MongoDB repository
sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list << EOF
deb https://repo.mongodb.org/apt/ubuntu $UBUNTU_CODENAME/mongodb-org/6.0 multiverse
EOF
wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo apt-key add -

# Install WireGuard, Pritunl Server and MongoDB
sudo apt update -y
sudo apt install wireguard wireguard-tools -y
sudo apt install pritunl mongodb-org -y

# Disable UFW and enable services
sudo ufw disable
sudo systemctl enable mongod pritunl --now
