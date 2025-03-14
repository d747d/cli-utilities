#!/bin/bash

# Check if all required arguments are provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <remote_host>"
    exit 1
fi

REMOTE_HOST=$1

# Function to generate a random password
generate_password() {
    local length=32
    tr -dc 'A-Za-z0-9' </dev/urandom | fold -w "$length" | head -n 1
}

# Generate a random password
PASSWORD=$(generate_password)

# Create a Shadowsocks-Rust configuration file
cat <<EOF > /tmp/ss_config.json
{
    "server": "0.0.0.0",
    "server_port": 8388,
    "local_address": "127.0.0.1",
    "local_port": 1080,
    "password": "$PASSWORD",
    "method": "chacha20-ietf-poly1305"
}
EOF

# Use SSH to transfer the configuration file to the remote host
scp /tmp/ss_config.json user@$REMOTE_HOST:/path/to/ss_config.json

# Start the Shadowsocks-Rust server on the remote host using SSH
ssh user@$REMOTE_HOST "ss-server -c /path/to/ss_config.json"

# Remove the temporary configuration file on the local machine
rm /tmp/ss_config.json

echo "Shadowsocks-Rust server started on $REMOTE_HOST with password: $PASSWORD"

