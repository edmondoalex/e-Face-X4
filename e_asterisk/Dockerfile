FROM ghcr.io/tech7fox/asterisk-hass-addon:6.2.0@sha256:3a2ef8f7a8efbe91926a65daf8ba8c4b6bfd9c0658c9874b45aee114fc936c83

COPY provisioner/ /opt/eface-provisioner/
COPY rootfs/ /

RUN chmod 0755 /etc/services.d/eface-provisioner/run \
    && chmod 0755 /etc/cont-init.d/eface-provisioner.sh \
    && printf '\n; e-Face managed endpoints (persistent addon_config)\n#include /config/asterisk/eface/pjsip.conf\n' >> /etc/asterisk/pjsip.conf \
    && python3 -m compileall -q /opt/eface-provisioner
