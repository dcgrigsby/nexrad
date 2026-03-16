#!/usr/bin/env bash

set -euo pipefail

# Launch the cxdb UI from its frontend directory
cd "/Users/dan/cxdb/frontend"
exec pnpm dev
