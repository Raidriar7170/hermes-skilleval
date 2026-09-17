FROM hermes-two-repo-clean:v3
RUN python -m pip install --no-cache-dir dictdiffer==0.9.0 pytest-runner==6.0.1
