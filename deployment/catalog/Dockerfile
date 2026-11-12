FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NSGABLACK_CATALOG_DB_MODE=off \
    NSGABLACK_CATALOG_HOSTED=1 \
    NSGABLACK_CATALOG_PROVIDERS="mlblack=mlblack.catalog.registry:get_catalog" \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    STREAMLIT_THEME_BASE=light \
    STREAMLIT_THEME_PRIMARY_COLOR="#087f72" \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    HOME=/tmp/catalog \
    XDG_CACHE_HOME=/tmp/catalog/cache

COPY requirements-web.txt /opt/catalog/requirements-web.txt
RUN python -m pip install --no-cache-dir --only-binary=:all: -r /opt/catalog/requirements-web.txt

# The build context is produced by package_context.py; it contains current source,
# not a Git archive, virtualenv, data store, model cache or private configuration.
COPY blackbase /opt/src/blackbase
COPY nsgablack /opt/src/nsgablack
COPY mlblack /opt/src/mlblack
COPY Dockerfile README.md package_context.py verify_release.py verify_ui.py verify_knowledge.py verify_search_filters.py verify_examples.py verify_navigation.py verify_lab.py verify_lab_ai.py build_examples.py run_example_receipts.py runtime.py auto_curate.py complete_catalog.py completion_worker.py gateway.conf verify_gateway.py /opt/catalog/
COPY release-manifest.json /opt/catalog/release-manifest.json
RUN python -m pip install --no-cache-dir --no-deps --no-build-isolation -e /opt/src/blackbase -e /opt/src/nsgablack -e /opt/src/mlblack \
    && python -m pip check \
    && groupadd --gid 10001 catalog \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /tmp/catalog --shell /usr/sbin/nologin catalog

# The hosted Catalog uses the verified source tree, including docs/example
# shards. Apply this after dependency installation to preserve the build cache.
ENV PYTHONPATH=/opt/src/nsgablack:/opt/src/blackbase/src:/opt/src
RUN python /opt/catalog/build_examples.py
# A private extraction umask on the deployment host must not make the public
# source/evidence tree unreadable to the UID 10001 web process. No secrets live here.
RUN chmod -R a+rX /opt/src /opt/catalog
ENV NSGABLACK_CATALOG_KNOWLEDGE_ENABLED=1 \
    NSGABLACK_CATALOG_KNOWLEDGE_INDEX=/opt/catalog/knowledge-sources.json \
    NSGABLACK_CATALOG_EXAMPLES_INDEX=/opt/catalog/examples.json

WORKDIR /opt/src/nsgablack
USER 10001:10001
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD ["python", "/opt/catalog/runtime.py", "health"]

# Bind all interfaces only inside the isolated container. The host mapping in
# README.md binds 127.0.0.1:8615, reached through SSH, without a public new port.
CMD ["python", "/opt/catalog/runtime.py", "serve"]
