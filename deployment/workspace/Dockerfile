ARG BASE_IMAGE=nsgablack-catalog:usage-guides-7ee0a449e194
FROM ${BASE_IMAGE}

# Reuse installed UI dependencies. This image contains only the cloud client
# overlay; the Project store, queue and execution remain in the local agent.
USER root
COPY lab_workspace.py lab_workspace_ui.py lab_workspace_transport.py lab_workspace_style.py lab_workspace_project.py lab_workspace_parameters.py lab_workspace_parameter_ui.py lab_workspace_results.py lab_workspace_reference.py lab_workspace_reference_ui.py lab_workspace_editor.py lab_workspace_navigation.py lab_workspace_review.py /opt/src/nsgablack/catalog/
COPY workspace_editor_frontend/ /opt/src/nsgablack/catalog/workspace_editor_frontend/
COPY workspace-manifest.json verify_frontend.py README.md Dockerfile /opt/workspace/
RUN chmod -R a+rX /opt/workspace /opt/src/nsgablack/catalog

ENV NSGABLACK_CATALOG_HOSTED=1 \
    NSGABLACK_CATALOG_DB_MODE=off \
    NSGABLACK_CATALOG_KNOWLEDGE_ENABLED=0 \
    NSGABLACK_PROJECT_WORKSPACE_ROOT="" \
    NSGABLACK_PROJECT_WORKSPACE_SOURCES="" \
    NSGABLACK_PROJECT_WORKSPACE_CLIENT_CONFIG=/run/secrets/workspace-client.json \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /opt/src/nsgablack
USER 10001:10001
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "/opt/workspace/verify_frontend.py", "--health", "--port", "18645"]
CMD ["python", "-m", "streamlit", "run", "/opt/src/nsgablack/catalog/lab_workspace_ui.py", "--server.address", "127.0.0.1", "--server.port", "18645", "--server.baseUrlPath", "apps/framework-workspace", "--server.headless", "true", "--server.maxMessageSize", "16", "--browser.gatherUsageStats", "false", "--theme.base", "dark", "--theme.backgroundColor", "#11151d", "--theme.secondaryBackgroundColor", "#191f2a", "--theme.textColor", "#dce3ef", "--theme.primaryColor", "#a5baff"]
