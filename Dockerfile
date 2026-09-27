# Kavach (कवच) - scam & paperwork checker for India, built on Sarvam AI.
#
#   docker build -t kavach .
#   docker run --rm -p 8000:8000 --env-file .env kavach
#
# SARVAM_API_KEY is supplied at runtime (-e / --env-file); it is never baked into the image.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg: normalises any uploaded recording to 16 kHz mono WAV for Saaras.
# fonts-noto-core: Indic script coverage for any server-side rendering.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin kavach
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=kavach:kavach kavach ./kavach
COPY --chown=kavach:kavach web ./web
COPY --chown=kavach:kavach samples ./samples

USER kavach
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

# --proxy-headers: trust X-Forwarded-* from the reverse proxy / load balancer in front.
CMD ["uvicorn", "kavach.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
