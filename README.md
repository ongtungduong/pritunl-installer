# How to use

## Clone the repository

First, clone the repository to **/tmp/pritunl-installer**:
```bash
git clone https://github.com/ongtungduong/pritunl-installer.git /tmp/pritunl-installer
```

## Install Pritunl (Server or Client)
Change directory to **/tmp/pritunl-installer** and run the **install.sh** script.

## Upgrade Pritunl Server
You will need to install and setup Pritunl before upgrading.

Change directory to **/tmp/pritunl-installer** and running the **upgrade.sh** script.

After upgrade, go to the management console and click on the **Upgrade to Enterprise**, then click on **Activate Subscription**.

Enter random license key and submit.

## Live on the edge

If you don't want to clone the repository, you can run the following command to install Pritunl (Server or Client).

```bash
bash <(curl -sSL https://github.com/ongtungduong/pritunl-installer/raw/main/install.sh)
```

And upgrade Pritunl Server by running the following command.

```bash
bash <(curl -sSL https://github.com/ongtungduong/pritunl-installer/raw/main/upgrade.sh)
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

