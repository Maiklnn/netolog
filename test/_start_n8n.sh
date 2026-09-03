#!/bin/bash
export NODES_EXCLUDE=[]
export N8N_HOST=0.0.0.0
export N8N_PORT=5678
export N8N_PROTOCOL=http
export N8N_EDITOR_BASE_URL=http://192.168.56.50:5678
export N8N_LISTEN_ON=public
export N8N_SECURE_COOKIE=false
export WEBHOOK_URL=http://192.168.56.50:5678/
setsid bash -c 'n8n start > /home/vagrant/n8n_output.log 2>&1' &
echo n8n started with PID $!