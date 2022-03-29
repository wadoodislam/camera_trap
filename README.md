# camera_trap
This repository holds the code that runs on Camera Traps.

## Setup Jetson Nano
- Python3 & Pip3
- Docker & Docker Compose

### Install Docker Compose via Python PIP
1. Upgrade pip3 using the following command:
```bash
python3 -m pip install --upgrade pip
```
2. Install Docker Compose build dependencies for Ubuntu.
```bash
sudo apt-get install -y libffi-dev python-openssl
```
3. Finally, install latest Docker Compose via pip
```bash
export DOCKER_COMPOSE_VERSION=1.29.2
sudo pip install docker-compose=="${DOCKER_COMPOSE_VERSION}"
```
Note: Above steps are referenced from this [guide](https://blog.hypriot.com/post/nvidia-jetson-nano-install-docker-compose/). 

