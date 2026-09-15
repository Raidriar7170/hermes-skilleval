FROM hermes-runtime-utility-executor:v1
RUN python -m pip install --no-cache-dir 'click==8.4.2' 'click-default-group==1.2.4' 'pluggy==1.6.0' 'python-dateutil==2.9.0.post0' 'sqlite-fts4==1.0.3' 'tabulate==0.10.0' 'setuptools==82.0.1' 'hypothesis==6.151.9' 'typing_extensions==4.15.0'
