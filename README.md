# garenController

Prereqs for RPi:
sudo apt update
sudo apt install -y python3-pip bluetooth bluez libdbus-1-dev
pip3 install bleak
# optional: run without sudo
sudo setcap 'cap_net_raw,cap_net_admin+eip' "$(readlink -f "$(which python3)")"
