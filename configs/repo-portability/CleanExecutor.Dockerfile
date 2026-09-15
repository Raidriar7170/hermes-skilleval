FROM node:22-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5 AS node_runtime
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254
COPY --from=node_runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node_runtime /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && npm install -g @openai/codex@0.154.0
RUN python -m pip install --no-cache-dir \
 'pandas==2.2.3' 'numpy==2.2.6' 'pytest==8.3.5' 'setuptools==82.0.1' 'wheel==0.45.1' \
 'click==8.4.2' 'click-default-group==1.2.4' 'pluggy==1.6.0' \
 'python-dateutil==2.9.0.post0' 'sqlite-fts4==1.0.3' 'tabulate==0.10.0' \
 'hypothesis==6.151.9' 'typing_extensions==4.15.0' \
 'agate==1.13.0' 'agate-excel==0.4.1' 'agate-dbf==0.2.4' 'agate-sql==0.7.2' \
 'openpyxl==3.1.5' 'sqlalchemy==2.0.48' 'xlrd==2.0.2'
