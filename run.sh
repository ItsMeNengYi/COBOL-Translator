#!/bin/bash

echo "Running your command"
cobc -x LOAN.cob -o LOAN
./LOAN
if command -v py >/dev/null 2>&1; then
  PYTHON_CMD=py
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD=python3
else
  PYTHON_CMD=python
fi

$PYTHON_CMD src/parser/parser.py
