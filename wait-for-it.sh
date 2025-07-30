#!/usr/bin/env bash

host="$1"
shift
cmd="$@"

echo "⏳ Waiting for $host..."
until nc -z ${host%:*} ${host#*:}; do
  sleep 1
done

echo "✅ $host is up! Starting app..."
exec "$@"
