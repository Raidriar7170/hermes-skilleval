#!/bin/bash
set -u

mkdir -p /logs/verifier

python3 /verifier/test_outputs.py > /logs/verifier/verifier_stdout.txt 2> /logs/verifier/verifier_stderr.txt || true

if [ ! -f /logs/verifier/reward.txt ]; then
  echo 0 > /logs/verifier/reward.txt
fi

# Copy artifacts for debugging
if [ -f "/root/data/openipf.xlsx" ]; then
  cp /root/data/openipf.xlsx /logs/verifier/openipf.xlsx
fi
