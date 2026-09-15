FROM hermes-repo-workflow:v2
RUN python -m pip install --no-cache-dir 'agate==1.13.0' 'agate-excel==0.4.1' 'agate-dbf==0.2.4' 'agate-sql==0.7.2' 'openpyxl==3.1.5' 'sqlalchemy==2.0.48' 'xlrd==2.0.2'
