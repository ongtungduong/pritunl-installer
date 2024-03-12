#!/bin/bash

printunl_version="1.30.3431.73"
ubuntu_codename="focal_amd64"
installation_directory="/usr/lib/pritunl/lib/python3.8/site-packages/pritunl"
handlers_subscription="https://gist.githubusercontent.com/ongtungduong/216d3d30f64f940f6813828746ab7e8b/raw/handlers.py"
subscription="https://gist.githubusercontent.com/ongtungduong/e844e488cf6a2b085dde1ac94d893d26/raw/subscription.py"

sudo wget https://github.com/pritunl/pritunl/releases/download/${printunl_version}/pritunl_${printunl_version}-0ubuntu1.${ubuntu_codename}.deb
sudo dpkg -i pritunl_${printunl_version}-0ubuntu1.${ubuntu_codename}.deb

sudo rm pritunl_${printunl_version}-0ubuntu1.${ubuntu_codename}.deb

curl ${handlers_subscription} | sudo tee ${installation_directory}/handlers/subscription.py
curl ${subscription} | sudo tee ${installation_directory}/subscription.py

sudo systemctl restart pritunl
