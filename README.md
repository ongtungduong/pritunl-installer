# Pritunl Installer

**Repository tested on Ubuntu 22.04 only.**

## Install Pritunl Server
Run the **install.sh** script or follow the instructions on the [Pritunl Homepage](https://pritunl.com/).

## Upgrade Pritunl Server

Find Pritunl directory in your system. For example: **/usr/lib/pritunl/usr/lib/python3.9/site-packages/pritunl**

Find your own url key and etag. (Or you can simply ask me)

Change values of url key and etag in the **subscription.py** file. And copy **enterprise.css.encrypted**, **subscription.py** and **handlers/subscription.py** files to the Pritunl directory.

Restart Pritunl service.

After upgrade, go to the management console and click on the **Upgrade to Enterprise**, then click on **Activate Subscription**.

Enter license key and submit.
