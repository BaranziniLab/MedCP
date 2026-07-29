#!/usr/bin/env bash
# Provision an AWS RDS MySQL instance, load the sham OMOP dataset into it, and
# create a dedicated SELECT-only reader, and write that reader (never the admin)
# to a protected local .dbenv for benchmarks/sham-dataset/test_backends.py. The
# file contains both MYSQL_* names and legacy DB_* compatibility aliases.
#
# Requires: aws CLI (configured), uv. Read the master password without echoing:
#     read -rsp 'RDS master password: ' DB_ADMIN_PASSWORD; echo
#     export DB_ADMIN_PASSWORD
#     ./provision.sh
#
# Override any of: AWS_REGION, DB_IDENTIFIER, DB_ADMIN_USER, DB_NAME, DB_CLASS,
# DB_READER_USER, DB_READER_PASSWORD. DB_USER/DB_PASSWORD remain supported as
# admin-input aliases for compatibility, but are written as reader aliases.
set -euo pipefail

REGION="${AWS_REGION:-us-west-2}"
ID="${DB_IDENTIFIER:-medcp-mysql}"
ADMIN_USER="${DB_ADMIN_USER:-${DB_USER:-medcpadmin}}"
ADMIN_PASSWORD="${DB_ADMIN_PASSWORD:-${DB_PASSWORD:-}}"
DB_NAME="${DB_NAME:-omop}"
CLASS="${DB_CLASS:-db.t3.micro}"
READER_USER="${DB_READER_USER:-medcpreader}"
MIGRATE_EXISTING="${MIGRATE_EXISTING:-0}"
: "${ADMIN_PASSWORD:?Set DB_ADMIN_PASSWORD (RDS master password, 8+ chars) before running}"
if [[ "$ADMIN_USER" == "$READER_USER" ]]; then
  echo "DB_READER_USER must differ from DB_ADMIN_USER" >&2
  exit 2
fi
READER_PASSWORD="${DB_READER_PASSWORD:-$(
  python3 -c 'import secrets, string; print("Aa1!" + "".join(secrets.choice(string.ascii_letters + string.digits + "-_") for _ in range(28)))'
)}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../../.." && pwd)"
export AWS_PAGER=""
umask 077
AWS_INPUT=""
DENV_TMP=""
cleanup() {
  [[ -z "$AWS_INPUT" ]] || rm -f "$AWS_INPUT"
  [[ -z "$DENV_TMP" ]] || rm -f "$DENV_TMP"
}
trap cleanup EXIT

if [[ "$MIGRATE_EXISTING" == "1" ]]; then
  echo "==> Locating existing RDS MySQL instance $ID"
  EP=$(aws rds describe-db-instances --region "$REGION" \
    --db-instance-identifier "$ID" \
    --query 'DBInstances[0].Endpoint.Address' --output text)
  echo "    endpoint: $EP"
else
  echo "==> Networking (default VPC + security group open to your IP on 3306)"
  MYIP=$(curl -s https://checkip.amazonaws.com | tr -d '\n')
  VPC=$(aws ec2 describe-vpcs --region "$REGION" --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
  SG=$(aws ec2 create-security-group --region "$REGION" --group-name medcp-test-sg \
        --description "MedCP backend databases" --vpc-id "$VPC" --query 'GroupId' --output text 2>/dev/null || \
       aws ec2 describe-security-groups --region "$REGION" --filters Name=group-name,Values=medcp-test-sg --query 'SecurityGroups[0].GroupId' --output text)
  aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG" --protocol tcp --port 3306 --cidr "${MYIP}/32" >/dev/null 2>&1 || true
  echo "    security group $SG (3306 open to ${MYIP})"

  echo "==> Creating RDS MySQL instance $ID ($CLASS)"
  AWS_INPUT="$(mktemp "${TMPDIR:-/tmp}/medcp-rds-input.XXXXXX")"
  MEDCP_AWS_MASTER_PASSWORD="$ADMIN_PASSWORD" \
  MEDCP_AWS_DB_ID="$ID" \
  MEDCP_AWS_DB_CLASS="$CLASS" \
  MEDCP_AWS_ADMIN_USER="$ADMIN_USER" \
  MEDCP_AWS_DB_NAME="$DB_NAME" \
  MEDCP_AWS_SECURITY_GROUP="$SG" \
  python3 -c '
import json
import os
import sys

json.dump(
    {
        "DBInstanceIdentifier": os.environ["MEDCP_AWS_DB_ID"],
        "DBInstanceClass": os.environ["MEDCP_AWS_DB_CLASS"],
        "Engine": "mysql",
        "MasterUsername": os.environ["MEDCP_AWS_ADMIN_USER"],
        "MasterUserPassword": os.environ["MEDCP_AWS_MASTER_PASSWORD"],
        "AllocatedStorage": 20,
        "DBName": os.environ["MEDCP_AWS_DB_NAME"],
        "VpcSecurityGroupIds": [os.environ["MEDCP_AWS_SECURITY_GROUP"]],
        "PubliclyAccessible": True,
        "BackupRetentionPeriod": 0,
        "MultiAZ": False,
        "DeletionProtection": False,
    },
    sys.stdout,
)
' > "$AWS_INPUT"
  aws rds create-db-instance --region "$REGION" \
    --cli-input-json "file://$AWS_INPUT" >/dev/null
  rm -f "$AWS_INPUT"
  AWS_INPUT=""
  echo "    waiting for it to become available (a few minutes)..."
  aws rds wait db-instance-available --region "$REGION" --db-instance-identifier "$ID"
  EP=$(aws rds describe-db-instances --region "$REGION" --db-instance-identifier "$ID" --query 'DBInstances[0].Endpoint.Address' --output text)
  echo "    endpoint: $EP"
fi

if [[ "$MIGRATE_EXISTING" == "1" ]]; then
  echo "==> Replacing the SELECT-only reader without reloading data"
  LOAD_MODE=(--reader-only)
else
  echo "==> Loading sham OMOP dataset as admin, then creating SELECT-only reader"
  LOAD_MODE=()
fi
MEDCP_DB_ADMIN_PASSWORD="$ADMIN_PASSWORD" \
MEDCP_DB_READER_PASSWORD="$READER_PASSWORD" \
uv run --directory "$REPO_ROOT" --locked \
  python "$HERE/../load_omop.py" mysql "$EP" "$ADMIN_USER" "$DB_NAME" 3306 \
  --reader-user "$READER_USER" "${LOAD_MODE[@]}"

write_export() {
  printf 'export %s=%q\n' "$1" "$2"
}

DENV_TMP="$(mktemp "$HERE/.dbenv.tmp.XXXXXX")"
{
  printf '%s\n' "# MySQL SELECT-only benchmark reader (plaintext; keep this file private)"
  write_export MYSQL_HOST "$EP"
  write_export MYSQL_PORT "3306"
  write_export MYSQL_USER "$READER_USER"
  write_export MYSQL_PASSWORD "$READER_PASSWORD"
  write_export MYSQL_DATABASE "$DB_NAME"
  printf '%s\n' "# Legacy compatibility aliases (also the SELECT-only reader)"
  write_export DB_USER "$READER_USER"
  write_export DB_PASSWORD "$READER_PASSWORD"
  write_export DB_NAME "$DB_NAME"
} > "$DENV_TMP"
chmod 600 "$DENV_TMP"
mv "$DENV_TMP" "$HERE/.dbenv"
DENV_TMP=""
trap - EXIT
unset ADMIN_PASSWORD READER_PASSWORD DB_ADMIN_PASSWORD DB_READER_PASSWORD DB_PASSWORD

echo "==> Wrote $HERE/.dbenv (git-ignored, mode 0600; SELECT-only reader only)."
echo "    Test: source \"$HERE/.dbenv\" && uv run --directory \"$REPO_ROOT\" --locked python benchmarks/sham-dataset/test_backends.py"
echo "    MedCP: map MYSQL_* to CLINICAL_RECORDS_* as shown in README; password not printed."
