#!/bin/sh
set -eu
auth=$(cat /run/secrets/neo4j_auth)
password=${auth#neo4j/}
exec cypher-shell -a bolt://127.0.0.1:7687 -u neo4j -p "$password" --format plain 'RETURN 1 AS ok;' >/dev/null
