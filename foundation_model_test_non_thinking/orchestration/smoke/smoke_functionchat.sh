#!/bin/bash
set -u
source "$(dirname "$0")/smoke_lib.sh"
smoke_one functionchat "$@"
