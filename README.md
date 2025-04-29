# Pritunl Installer

**Repository tested on Ubuntu 22.04 (Jammy) with Pritunl version 1.32.4181.41.**

## Install Pritunl Server
Run the **install.sh** script or follow the instructions on the [Pritunl Homepage](https://pritunl.com/).

## Upgrade Pritunl Server

Change the values of PRITUNL_URL_KEY, PRITUNL_ETAG and PRITUNL_HOME_DIR in the **constants.py** file.

Copy **data.encrypted**, **subscription.py**, **constants.py** and **handlers/subscription.py** files to the Pritunl directory.

Restart Pritunl service.

After upgrade, go to the management console and click on the **Upgrade to Enterprise**, then click on **Activate Subscription**.

Enter license key and submit.
