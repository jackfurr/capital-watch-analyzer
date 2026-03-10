#!/bin/bash
# Weekly report generation cron script
# Add to crontab: 0 9 * * 3 /path/to/run-weekly.sh

set -e

cd "$(dirname "$0")"

# Load environment
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run the scheduler
python -m src.cli schedule
