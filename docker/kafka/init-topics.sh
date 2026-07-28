#!/bin/bash
# RecoStack — Initialize Redpanda Topics
# Run this after Redpanda is started, from inside the container or via
#   docker exec <container> rpk topic create ...
#
# Creates the "user-events" topic that will carry all user interaction events
# (ratings, clicks, purchases) for real-time feature computation.

set -euo pipefail

RPK_BROKERS="${RPK_BROKERS:-localhost:9092}"

echo "Creating topic 'user-events' on broker(s): $RPK_BROKERS"

rpk topic create "user-events" \
  --brokers "$RPK_BROKERS" \
  --partitions 3 \
  --replicas 1

echo "Topic 'user-events' created successfully."

# Verify it exists
echo ""
echo "Verifying topics:"
rpk topic list --brokers "$RPK_BROKERS"