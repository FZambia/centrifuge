Vagrant
=============================

A ready-to-go hybrid development environment for building and running Centrifuge.

It was built to make it easier for developers to build centrifuge from the source directory, and especially for Windows users to get a complete dev environment set up without all the headaches.

### Installation

To install, download and install [Vagrant](https://www.vagrantup.com/downloads.html) for your platform, then download and install [VirtualBox](http://virtualbox.org/).

Once Vagrant and VirtualBox are installed, you can download the latest release of this GitHub repo, and unzip it. `cd` into the unzipped folder and run:

```bash
$ vagrant up
$ vagrant ssh
```

This will download and install the image, and then go through the dependencies and install them one by one. `vagrant ssh` will connect you to the image and give you a bash prompt. 

### Configuration

Once everything completes, you'll have a working bash script to manually start centrifuge. 
You can edit start.sh to configure port, log file, config json file, database engine.
You can use the data directory to put and keep your own centrifuge.db and centrifuge.json. This is useful to keep permanent centrifuge configuration for your projects (at least for development).
By default, the port is 8000 but you can also edit `Vagrantfile` and `start.sh` to configure another port.

```bash
$ /vagrant/start.sh
```

To compile again:

```bash
$ cd /home/centrifuge
$ sudo python setup.py install
```

Now you can use http://localhost:8000/ to play with centrifuge under Windows, Linux or Mac OS.
