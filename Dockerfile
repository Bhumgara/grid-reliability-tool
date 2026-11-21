# Grid Reliability backend: one image for the API and the refresh worker.
#
#   docker build -t grid-reliability .
#   docker run -p 8000:8000 -v grid-data:/data grid-reliability                 # API
#   docker run -v grid-data:/data -e DEPLOYMENT_BUNDLE_URL=... \
#     grid-reliability python -m backend.worker                                # worker
#
# Data lives on the /data volume (GRID_DATA_DIR), shared by both. The image
# holds only the code, the SQL and the trained model (artifacts/).

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GRID_DATA_DIR=/data \
    PORT=8000

WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY requirements-backend.txt .
RUN pip install -r requirements-backend.txt

# Only what the API and worker import or read at run time.
COPY core/ core/
COPY backend/ backend/
COPY pipelines/ pipelines/
COPY model/ model/
COPY sql/ sql/
COPY artifacts/ artifacts/

# Run as an unprivileged user that owns the data folder.
RUN useradd --create-home --uid 10001 grid \
    && mkdir -p /data \
    && chown grid:grid /data
USER grid

EXPOSE 8000

# The API by default. PORT can be overridden (Cloud Run sets it). Run the
# worker by passing a different command: python -m backend.worker [--once].
CMD ["sh", "-c", "exec uvicorn backend.api.main:app --host 0.0.0.0 --port \"$PORT\""]
