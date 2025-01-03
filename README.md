## Installation

### Install Pritunl Server
```bash
bash <(curl -sSL https://github.com/ongtungduong/quick-installers/raw/main/pritunl/install.sh)
```

### Upgrade Pritunl Server
```bash
bash <(curl -sSL https://github.com/ongtungduong/quick-installers/raw/main/pritunl/upgrade.sh)
```

### Install Pritunl Client
```bash
INSTALLATION_TYPE="client" bash <(curl -sSL https://github.com/ongtungduong/quick-installers/raw/main/pritunl/install.sh)
```

## Configuration

### Increase Open File Limit
```bash
echo "* hard nofile 64000" | sudo tee -a /etc/security/limits.conf
echo "* soft nofile 64000" | sudo tee -a /etc/security/limits.conf
echo "root hard nofile 64000" | sudo tee -a /etc/security/limits.conf
echo "root soft nofile 64000" | sudo tee -a /etc/security/limits.conf
```

### Load Balancing
```bash
sudo pritunl set app.reverse_proxy true
sudo pritunl set app.redirect_server false
sudo pritunl set app.server_ssl false
sudo pritunl set app.server_port 80
```

