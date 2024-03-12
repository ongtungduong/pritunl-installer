#!/bin/bash

printunl_version="1.30.3431.73"
ubuntu_codename="jammy_amd64"
installation_directory="/usr/lib/pritunl/lib/python3.10/site-packages/pritunl"
handlers_subscription="https://raw.githubusercontent.com/ongtungduong/pritunl-installer/main/handlers-subscription.py"
subscription="https://raw.githubusercontent.com/ongtungduong/pritunl-installer/main/subscription.py"

wget https://github.com/pritunl/pritunl/releases/download/${printunl_version}/pritunl_${printunl_version}-0ubuntu1.${ubuntu_codename}.deb
sudo dpkg -i pritunl_${printunl_version}-0ubuntu1.${ubuntu_codename}.deb

rm pritunl_${printunl_version}-0ubuntu1.${ubuntu_codename}.deb

curl ${handlers_subscription} | sudo tee ${installation_directory}/handlers/subscription.py
curl ${subscription} | sudo tee ${installation_directory}/subscription.py

sudo systemctl restart pritunl
