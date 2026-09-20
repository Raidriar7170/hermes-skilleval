# Preserve the inherited Codex executable/isolation, add the public Python test runtime.
FROM python:3.11-slim AS python_runtime
FROM hermes-asi-executor:v1
COPY --from=python_runtime /usr/local/ /usr/local/
RUN python -m pip install --no-cache-dir \
    pytest==8.3.5 pytest-mock==3.14.0 pytest-forked==1.6.0 mock==5.2.0 \
    PyYAML==6.0.2 jinja2==3.0.3 MarkupSafe==2.1.5 cryptography==44.0.3 \
    packaging==24.2 resolvelib==0.5.4 passlib==1.7.4 bcrypt==4.3.0 \
    pexpect==4.9.0 pytz==2024.2 six==1.17.0
ENV PYTHONDONTWRITEBYTECODE=1
