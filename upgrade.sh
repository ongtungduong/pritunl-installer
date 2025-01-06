#!/bin/bash

# Version 1.30.3431.73 is the latest version successfully tested with this repository. So we need to downgrade to this version.
# TODO: Update this version to the latest version
VERSION="1.30.3431.73"
CODENAME=$(lsb_release -cs)

# Download and downgrade Pritunl
sudo wget https://github.com/pritunl/pritunl/releases/download/${VERSION}/pritunl_${VERSION}-0ubuntu1.${CODENAME}_amd64.deb
sudo dpkg -i pritunl_${VERSION}-0ubuntu1.${CODENAME}_amd64.deb

# Clean up
sudo rm pritunl_${VERSION}-0ubuntu1.${CODENAME}_amd64.deb

# Replace subscription files
PYTHON=$( [ $CODENAME = "focal" ] && echo "python3.8" || echo "python3.10" )
DIRECTORY="/usr/lib/pritunl/lib/$PYTHON/site-packages/pritunl"
REPO="https://github.com/ongtungduong/pritunl-installer/raw/main"

if [ ! -f /tmp/pritunl-installer/handlers/subscription.py ] || [ ! -f /tmp/pritunl-installer/subscription.py ]; then
    curl -sSL ${REPO}/handlers/subscription.py | sudo tee ${DIRECTORY}/handlers/subscription.py > /dev/null
    curl -sSL ${REPO}/subscription.py | sudo tee ${DIRECTORY}/subscription.py > /dev/null
else
    sudo cp -f /tmp/pritunl-installer/handlers/subscription.py ${DIRECTORY}/handlers/subscription.py
    sudo cp -f /tmp/pritunl-installer/subscription.py ${DIRECTORY}/subscription.py
fi

# Restart Pritunl
sudo systemctl restart pritunl