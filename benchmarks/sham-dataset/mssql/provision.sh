#!/usr/bin/env bash
# Provision an AWS RDS SQL Server (Express) instance, load the sham OMOP dataset
# into it, and write a local .dbenv (git-ignored) for
# benchmarks/sham-dataset/test_backends.py. The file contains both MSSQL_* names
# and legacy DB_* compatibility aliases.
#
# Requires: aws CLI (configured), uv. Read the master password without echoing:
#     read -rsp 'RDS master password: ' DB_PASSWORD; echo; export DB_PASSWORD
#     ./provision.sh
#
# Override any of: AWS_REGION, DB_IDENTIFIER, DB_USER, DB_NAME, DB_CLASS.
set -euo pipefail

REGION="${AWS_REGION:-us-west-2}"
ID="${DB_IDENTIFIER:-medcp-mssql}"
DB_USER="${DB_USER:-medcpadmin}"
DB_NAME="${DB_NAME:-omop}"
CLASS="${DB_CLASS:-db.t3.small}"
: "${DB_PASSWORD:?Set DB_PASSWORD (RDS master password, 8+ chars) before running}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../../.." && pwd)"
export AWS_PAGER=""

echo "==> Networking (default VPC + security group open to your IP on 1433)"
MYIP=$(curl -s https://checkip.amazonaws.com | tr -d '\n')
VPC=$(aws ec2 describe-vpcs --region "$REGION" --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
SG=$(aws ec2 create-security-group --region "$REGION" --group-name medcp-test-sg \
      --description "MedCP backend databases" --vpc-id "$VPC" --query 'GroupId' --output text 2>/dev/null || \
     aws ec2 describe-security-groups --region "$REGION" --filters Name=group-name,Values=medcp-test-sg --query 'SecurityGroups[0].GroupId' --output text)
aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG" --protocol tcp --port 1433 --cidr "${MYIP}/32" >/dev/null 2>&1 || true
echo "    security group $SG (1433 open to ${MYIP})"

echo "==> Creating RDS SQL Server Express instance $ID ($CLASS)"
aws rds create-db-instance --region "$REGION" --db-instance-identifier "$ID" \
  --db-instance-class "$CLASS" --engine sqlserver-ex --license-model license-included \
  --master-username "$DB_USER" --master-user-password "$DB_PASSWORD" --allocated-storage 20 \
  --vpc-security-group-ids "$SG" --publicly-accessible --backup-retention-period 0 \
  --no-multi-az --no-deletion-protection >/dev/null
echo "    waiting for it to become available (SQL Server takes ~10-15 min)..."
aws rds wait db-instance-available --region "$REGION" --db-instance-identifier "$ID"
EP=$(aws rds describe-db-instances --region "$REGION" --db-instance-identifier "$ID" --query 'DBInstances[0].Endpoint.Address' --output text)
echo "    endpoint: $EP"

echo "==> Loading sham OMOP dataset into SQL Server (creates database '$DB_NAME')"
uv run --directory "$REPO_ROOT" --locked \
  python "$HERE/../load_omop.py" mssql "$EP" "$DB_USER" "$DB_PASSWORD" "$DB_NAME" 1433

write_export() {
  printf 'export %s=%q\n' "$1" "$2"
}

umask 077
DENV_TMP="$(mktemp "$HERE/.dbenv.tmp.XXXXXX")"
trap 'rm -f "$DENV_TMP"' EXIT
{
  printf '%s\n' "# SQL Server benchmark connection (plaintext; keep this file private)"
  write_export MSSQL_HOST "$EP"
  write_export MSSQL_PORT "1433"
  write_export MSSQL_USER "$DB_USER"
  write_export MSSQL_PASSWORD "$DB_PASSWORD"
  write_export MSSQL_DATABASE "$DB_NAME"
  printf '%s\n' "# Legacy compatibility aliases"
  write_export DB_USER "$DB_USER"
  write_export DB_PASSWORD "$DB_PASSWORD"
  write_export DB_NAME "$DB_NAME"
} > "$DENV_TMP"
chmod 600 "$DENV_TMP"
mv "$DENV_TMP" "$HERE/.dbenv"
trap - EXIT

echo "==> Wrote $HERE/.dbenv (git-ignored, mode 0600; contains plaintext credentials)."
echo "    Test: source \"$HERE/.dbenv\" && uv run --directory \"$REPO_ROOT\" --locked python benchmarks/sham-dataset/test_backends.py"
echo "    MedCP: map MSSQL_* to CLINICAL_RECORDS_* as shown in README; password not printed."
