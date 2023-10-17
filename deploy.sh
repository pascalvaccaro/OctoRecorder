#!/bin/bash


rsync -r -R -e ssh ./ --include='.py$'  patch@192.168.1.29:~/OctoRecorder/
read -p "Done uploading. Run program? (y/n) " -n 1
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
	ssh -i ~/.ssh/id_rsa patch@192.168.1.29 "python3 ~/OctoRecorder/main.py"
fi
