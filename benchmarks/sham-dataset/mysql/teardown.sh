#!/usr/bin/env bash
# Delete the RDS MySQL instance created by provision.sh (stops billing).
set -euo pipefail
REGION="${AWS_REGION:-us-west-2}"
ID="${DB_IDENTIFIER:-medcp-mysql}"
export AWS_PAGER=""
echo "Deleting RDS instance $ID ..."
aws rds delete-db-instance --region "$REGION" --db-instance-identifier "$ID" \
  --skip-final-snapshot --delete-automated-backups >/dev/null
aws rds wait db-instance-deleted --region "$REGION" --db-instance-identifier "$ID"
rm -f "$(cd "$(dirname "$0")" && pwd)/.dbenv"
echo "Deleted $ID. (The shared 'medcp-test-sg' security group is left in place;"
echo "remove it manually once no MedCP test instances remain.)"
