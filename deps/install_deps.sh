#!/bin/bash
export SIDEKICK_HOME=$HOME/sidekick

# exit if any errors
set -e

# git submodules
cd $SIDEKICK_HOME
git submodule init
git submodule update
cd $SIDEKICK_HOME/http3_integration/quiche
git submodule init
git submodule update

# Linux dependencies
sudo apt-get update -y
sudo apt-get install -y curl ethtool
sudo apt-get install -y texlive # pari
sudo apt-get install -y autoconf libtool  # curl
sudo apt-get install -y cmake libpcre3 libpcre3-dev zlib1g zlib1g-dev libssl-dev  # nginx
sudo apt-get install -y libnfnetlink-dev  # pepsal
sudo apt-get install -y mininet python3-pip  # mininet
sudo apt-get install -y python3-virtualenv  # plotting

# mininet
pip3 install mininet

# plotting scripts
sudo pip install virtualenv
sudo pip install virtualenvwrapper
cd $SIDEKICK_HOME/figures
virtualenv -p python3 env

# rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh  # hit 1
source $HOME/.cargo/env

# build a separate quiche directory for nginx to link to (vs curl)
cd $SIDEKICK_HOME/deps/
git clone --recurse-submodules git@github.com:ygina/quiche.git quiche-nginx
cd quiche-nginx
git checkout sidekick

# Download external dependencies
cd $SIDEKICK_HOME/deps
curl -O https://nginx.org/download/nginx-1.16.1.tar.gz
tar xvzf nginx-1.16.1.tar.gz
wget https://pari.math.u-bordeaux.fr/pub/pari/OLD/2.15/pari-2.15.2.tar.gz
tar xvzf pari-2.15.2.tar.gz
git clone git@github.com:viveris/pepsal.git
rm nginx-1.16.1.tar.gz pari-2.15.2.tar.gz

