#!/usr/bin/env bash
# Provision an AWS RDS MySQL instance, load the sham OMOP dataset into it, and
# write a local .dbenv (git-ignored) for benchmarks/sham-dataset/test_backends.py.
#
# Requires: aws CLI (configured), uv. Set the master password first:
#     export DB_PASSWORD='SomeStrongPassword123'
#     ./provision.sh
#
# Override any of: AWS_REGION, DB_IDENTIFIER, DB_USER, DB_NAME, DB_CLASS.
set -euo pipefail

REGION="${AWS_REGION:-us-west-2}"
ID="${DB_IDENTIFIER:-medcp-mysql}"
DB_USER="${DB_USER:-medcpadmin}"
DB_NAME="${DB_NAME:-omop}"
CLASS="${DB_CLASS:-db.t3.micro}"
: "${DB_PASSWORD:?Set DB_PASSWORD (RDS master password, 8+ chars) before running}"
HERE="$(cd "$(dirname "$0")" && pwd)"
export AWS_PAGER=""

echo "==> Networking (default VPC + security group open to your IP on 3306)"
MYIP=$(curl -s https://checkip.amazonaws.com | tr -d '\n')
VPC=$(aws ec2 describe-vpcs --region "$REGION" --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
SG=$(aws ec2 create-security-group --region "$REGION" --group-name medcp-test-sg \
      --description "MedCP backend databases" --vpc-id "$VPC" --query 'GroupId' --output text 2>/dev/null || \
     aws ec2 describe-security-groups --region "$REGION" --filters Name=group-name,Values=medcp-test-sg --query 'SecurityGroups[0].GroupId' --output text)
aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG" --protocol tcp --port 3306 --cidr "${MYIP}/32" >/dev/null 2>&1 || true
echo "    security group $SG (3306 open to ${MYIP})"

echo "==> Creating RDS MySQL instance $ID ($CLASS)"
aws rds create-db-instance --region "$REGION" --db-instance-identifier "$ID" \
  --db-instance-class "$CLASS" --engine mysql --master-username "$DB_USER" \
  --master-user-password "$DB_PASSWORD" --allocated-storage 20 --db-name "$DB_NAME" \
  --vpc-security-group-ids "$SG" --publicly-accessible --backup-retention-period 0 \
  --no-multi-az --no-deletion-protection >/dev/null
echo "    waiting for it to become available (a few minutes)..."
aws rds wait db-instance-available --region "$REGION" --db-instance-identifier "$ID"
EP=$(aws rds describe-db-instances --region "$REGION" --db-instance-identifier "$ID" --query 'DBInstances[0].Endpoint.Address' --output text)
echo "    endpoint: $EP"

echo "==> Loading sham OMOP dataset into MySQL"
uv run --no-project --with pymysql python3 "$HERE/../load_omop.py" mysql "$EP" "$DB_USER" "$DB_PASSWORD" "$DB_NAME" 3306

cat > "$HERE/.dbenv" <<EOF
export MYSQL_HOST=$EP
export MYSQL_PORT=3306
export DB_USER=$DB_USER
export DB_PASSWORD=$DB_PASSWORD
export DB_NAME=$DB_NAME
EOF
echo "==> Wrote $HERE/.dbenv (git-ignored)."
echo "    Test:  source $HERE/.dbenv && python benchmarks/sham-dataset/test_backends.py"
echo "    MedCP: CLINICAL_RECORDS_BACKEND=mysql CLINICAL_RECORDS_SERVER=$EP \\"
echo "           CLINICAL_RECORDS_DATABASE=$DB_NAME CLINICAL_RECORDS_USERNAME=$DB_USER CLINICAL_RECORDS_PASSWORD=***"
