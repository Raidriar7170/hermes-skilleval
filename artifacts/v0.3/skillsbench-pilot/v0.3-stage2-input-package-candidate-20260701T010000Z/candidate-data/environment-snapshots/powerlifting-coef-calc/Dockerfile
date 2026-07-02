FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1

# Create working directory
WORKDIR /root

# Copy the Excel file to /root/
RUN mkdir -p /root/data
COPY openipf_cleaned.xlsx /root/data/openipf.xlsx
COPY data-readme.md /root/data/data-readme.md

CMD ["/bin/bash"]
