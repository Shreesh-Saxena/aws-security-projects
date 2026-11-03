# BUILD — Project 2: Secure VPC (three‑tier network)

A complete, reproducible step‑by‑step runbook. Built by hand in the **console** (for the
screenshots), then codified as CloudFormation. Build everything in **one region** and the
two private subnets in **two different AZs** (RDS needs two).

> **Cost:** the **NAT Gateway** and **RDS** are *not* free‑tier — build, verify, then tear
> down the **same day**. Everything else (VPC, subnets, route tables, IGW, SGs) is free.

---

## Prerequisites
- AWS account, admin console access. Know your public IP (for the SSH rule): https://checkip.amazonaws.com

---

## Step 1 — VPC and subnets
1. VPC → **Create VPC** → *VPC only* (not the wizard — build each piece to understand it).
   CIDR `10.0.0.0/16`, name `secure-vpc`.
2. Create **3 subnets**:
   - `public-1a`  `10.0.1.0/24`  (AZ **a**)
   - `private-1a` `10.0.2.0/24`  (AZ **a**)
   - `private-1b` `10.0.3.0/24`  (AZ **b**) ← different AZ, for RDS

## Step 2 — Internet Gateway + NAT Gateway
1. **Internet Gateway** → create → **attach** to `secure-vpc`.
2. **NAT Gateway** → create in `public-1a`, **Connectivity = Public**, **Allocate Elastic IP**.
   (Billing starts here.)

## Step 3 — Route tables
1. **public-rt:** route `0.0.0.0/0 → Internet Gateway`; **associate** `public-1a`.
2. **private-rt:** route `0.0.0.0/0 → NAT Gateway`; **associate** both private subnets.
   - "Public" vs "private" is purely this routing difference.

## Step 4 — Security groups (chained by reference, not IP)
Create three, each allowing only the tier above it:
- **web-sg:** inbound `80, 443` from `0.0.0.0/0`; `22` from **your IP/32**.
- **app-sg:** inbound `8080, 22` from **web-sg** (source = the security group, not a CIDR).
- **db-sg:**  inbound `3306` from **app-sg**.

Give every rule a Description (Checkov likes it, and it documents intent).

## Step 5 — Compute (web + app)
1. **web EC2:** Amazon Linux, in `public-1a`, **auto‑assign public IP ON**, SG `web-sg`,
   user‑data installing `httpd` and writing a page. Open its public IP in a browser → page loads.
2. **app EC2:** Amazon Linux, in `private-1a`, **no public IP**, SG `app-sg`.

## Step 6 — Database (private RDS MySQL)
1. **DB subnet group** over the two private subnets (`private-1a`, `private-1b`).
2. **RDS → Create database → MySQL**, template Free/Dev, **Single‑AZ**, `db.t3.micro`,
   **Public access = No**, VPC = `secure-vpc`, SG = `db-sg`. (Use
   `ManageMasterUserPassword` so Secrets Manager holds the password — no secret typed in.)

## Step 7 — Verify (don't assume)

**Reachability Analyzer** (one path at a time — VPC → Reachability Analyzer):

| Path | Expected | Why |
|------|----------|-----|
| Internet → app EC2 | ❌ Not reachable | no public IP **and** app‑sg (two layers) |
| web EC2 → app EC2 | ✅ Reachable | app‑sg allows web‑sg |
| app EC2 → RDS | ✅ Reachable | db‑sg allows app‑sg :3306 |
| Internet → RDS | ❌ Not reachable | private, public access off |

**Network Access Analyzer** (whole‑network audit): use the Amazon‑managed
**All‑IGW‑Ingress** scope → every finding points only to the **web tier** (80/443/22); no
internet path to app EC2 or RDS. Screenshot both tools' results + the live web page.

## Infrastructure as Code (CloudFormation)
The whole stack (22 resources) is codified in
[`cloudformation/template.yaml`](cloudformation/template.yaml):
```bash
aws cloudformation deploy \
  --stack-name project2-secure-vpc \
  --template-file cloudformation/template.yaml \
  --parameter-overrides SshAllowedCidr=<your-ip>/32

aws cloudformation delete-stack --stack-name project2-secure-vpc
```
AMI comes from an SSM public parameter; the RDS password is generated/stored by Secrets
Manager (`ManageMasterUserPassword`) — no secret in the template.

## Security scanning
```bash
cfn-lint cloudformation/template.yaml
python -m checkov.main -f cloudformation/template.yaml
```
Fixed: RDS `StorageEncrypted`, `EnableIAMDatabaseAuthentication`, SG rule Descriptions.
Kept intentionally (with reason): HTTP 80 open (public web server is the point); SSH 22
(restrict with `SshAllowedCidr=<your-ip>/32`); RDS Multi‑AZ/enhanced‑monitoring off
(cost‑controlled lab). See README for the full review.

## Cost & cleanup (same day)
Order: **RDS** delete → **EC2** terminate → **NAT Gateway** delete → **Elastic IP** release →
**DB subnet group** delete → **VPC** delete (cascades subnets, route tables, IGW, SGs).
With CloudFormation this is one `delete-stack`.

---

*Part of [aws-security-projects](../README.md).*
