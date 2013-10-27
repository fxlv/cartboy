#!/bin/bash
VERSION="0.1-1"
PKG_DIR="debian/cartboy_${VERSION}"

mkdir -p $PKG_DIR/usr/bin
mkdir -p $PKG_DIR/etc/cartboy/applications
cp -av debian/DEBIAN $PKG_DIR/

cp -v cartboy.py ${PKG_DIR}/usr/bin/
cp -v examples/conf/cartboy.conf ${PKG_DIR}/etc/cartboy/cartboy.conf
chmod +x ${PKG_DIR}/usr/bin/cartboy.py
sudo chown -R root:root $PKG_DIR
dpkg-deb --build $PKG_DIR
sudo rm -rfv $PKG_DIR
