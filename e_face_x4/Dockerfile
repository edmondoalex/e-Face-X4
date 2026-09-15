FROM ghcr.io/home-assistant/base:3.21

ARG BUILD_VERSION=dev
ARG BUILD_ARCH=unknown

LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EFACE_VERSION="${BUILD_VERSION}" \
    PYTHONPATH=/app \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN apk add --no-cache python3 py3-pip \
    && python3 -m venv "$VIRTUAL_ENV" \
    && "$VIRTUAL_ENV/bin/pip" install --no-cache-dir --upgrade pip setuptools wheel

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN "$VIRTUAL_ENV/bin/pip" install --no-cache-dir -r /app/requirements.txt
COPY app /app/app
COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh && "$VIRTUAL_ENV/bin/python" -m compileall -q /app/app

CMD ["/app/run.sh"]
