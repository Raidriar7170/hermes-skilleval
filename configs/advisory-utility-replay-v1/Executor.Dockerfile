FROM hermes-advisory-tools:fixed AS tools
FROM hermes-advisory-python:fixed
COPY --from=tools /usr/local/bin/node /usr/local/bin/node
COPY --from=tools /usr/local/lib/node_modules/@openai /usr/local/lib/node_modules/@openai
RUN ln -s ../lib/node_modules/@openai/codex/bin/codex.js /usr/local/bin/codex
COPY wheels /opt/wheels
RUN python -m pip install --no-index --no-deps /opt/wheels/*.whl && rm -rf /opt/wheels
RUN python -m pip install --no-cache-dir pytest==8.3.5 pluggy==1.6.0 iniconfig==2.1.0
