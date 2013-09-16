#!/bin/bash
version="$1"
echo "building rpm with version $version"
rpmbuild -bb centrifuge.spec --define "version $version" --define "release `date +%s`" --define "source $(cd ..;pwd)"