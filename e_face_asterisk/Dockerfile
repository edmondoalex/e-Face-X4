FROM ghcr.io/tech7fox/asterisk-hass-addon:6.2.0

ARG BUILD_VERSION=6.2.0-eface.10
ARG BUILD_ARCH=amd64

COPY asterisk_provisioner/ /opt/eface/asterisk_provisioner/
COPY rootfs/ /

ENV PYTHONPATH=/opt/eface

RUN chmod 0755 /etc/cont-init.d/zz-eface-provisioner.sh /etc/services.d/eface_provisioner/run

LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}"
