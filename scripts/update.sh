#!/bin/bash

# Script to update Pritunl to the latest version
# Latest version: 1.32.4181.41

version="1.32.4181.41"
codename="jammy"
wget https://github.com/pritunl/pritunl/releases/download/${version}/pritunl_${version}-0ubuntu1.${codename}_amd64.deb
dpkg -i pritunl_${version}-0ubuntu1.${codename}_amd64.deb