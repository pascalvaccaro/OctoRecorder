#!/bin/bash

scp -q -i ~/.ssh/id_rsa *.pd *.py patch@192.168.1.29:/usr/local/puredata-patches/OctoRecorder/
read -p "Done uploading. Run program? (y/n) " -n 1
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
	ssh -i ~/.ssh/id_rsa patch@192.168.1.29 "sh /usr/local/patchbox-modules/puredata/launch.sh /usr/local/puredata-patches/OctoRecorder/main.pd"
fi
