#!/bin/sh
set -e

if [ -e /.installed ]; then
  echo 'Already installed.'
else
  echo ''
  echo 'INSTALLING'
  echo '----------'

  cd /home/centrifuge
    
  apt-get update
  apt-get install -y build-essential python-dev python-pip
  
  python setup.py install

  touch /.installed
fi

