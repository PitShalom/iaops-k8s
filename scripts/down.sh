#!/usr/bin/env bash
# Remove o cluster Kind do laboratório.
set -euo pipefail
kind delete cluster --name iaops
