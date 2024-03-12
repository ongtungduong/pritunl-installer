#!/bin/bash

sudo ufw disable

echo "deb http://repo.pritunl.com/stable/apt $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/pritunl.list

sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list << EOF
deb https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/6.0 multiverse
EOF

curl -fsSL https://www.mongodb.org/static/pgp/server-6.0.asc|sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/mongodb-6.gpg

curl -fsSL  https://raw.githubusercontent.com/pritunl/pgp/master/pritunl_repo_pub.asc|sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/pritunl.gpg

sudo apt update -y

sudo apt install wireguard wireguard-tools -y
sudo apt install pritunl mongodb-org -y

sudo systemctl enable pritunl mongod
sudo systemctl start pritunl mongod
