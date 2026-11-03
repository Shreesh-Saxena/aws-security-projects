# BUILD — Project 1: IAM Least‑Privilege Access to S3

A complete, reproducible step‑by‑step runbook. Built by hand in the **console** (for the
screenshots), then codified as CloudFormation. Replace the placeholder account id
`111122223333` and use a globally‑unique bucket name.

> IAM is global, but create the S3 bucket in a region near you. No access keys are needed —
> everything is console + the IAM Policy Simulator.

---

## Prerequisites
- AWS account; sign in as an IAM **admin** user (not root).
- A test bucket name that is globally unique, e.g. `myname-iam-demo`.

---

## Part 1 — Scoped identity policy (read only `reports/`)

**Goal:** user `Alice` can read only the `reports/` prefix of one bucket — nothing else.

1. **Bucket + objects:** S3 → create bucket `myname-iam-demo` (Block Public Access ON).
   Inside it create a folder `reports/` and upload `reports/hello.txt`. Also upload a
   `secret.txt` at the bucket root (to prove it stays unreadable).
2. **Policy:** IAM → Policies → **Create policy** → JSON → paste
   [`policies/S3ReportsReadOnly.json`](policies/S3ReportsReadOnly.json) (set your bucket name).
   Two least‑privilege decisions:
   - `s3:ListBucket` is gated by `Condition: s3:prefix = reports/*` (can't list the root).
   - `s3:GetObject` is scoped to `bucket/reports/*` (can't read files elsewhere).
   Name it `S3ReportsReadOnly`.
3. **Group:** IAM → User groups → create `reports-readers` → attach `S3ReportsReadOnly`.
   (Attach permissions to the **group**, not the user — adding auditors later is just group membership.)
4. **User:** IAM → Users → create `Alice` (console access), add to `reports-readers`.

**Verify (sign in as Alice, or use the Policy Simulator):**

| # | Action | Expected |
|---|--------|----------|
| 1 | Download `reports/hello.txt` | ✅ Allow |
| 2 | List all buckets | ❌ Deny |
| 3 | List the bucket **root** (no prefix) | ❌ Deny (prefix condition) |
| 4 | Upload to `reports/` | ❌ Deny (no write) |
| 5 | Read `secret.txt` (root) | ❌ Deny (out of scope) |

Screenshot each allowed/denied result.

## Part 2 — Role assumption (trust policy vs permission policy)

**Goal:** user `bob` has **no** S3 access; he reads reports **only** by assuming a role.

1. **User `bob`:** create the user. Give him **one** inline policy only —
   [`policies/bob-assume-role.json`](policies/bob-assume-role.json) (`sts:AssumeRole` on the
   role ARN). He gets nothing else.
2. **Role:** IAM → Roles → Create role → **Custom trust policy** → paste
   [`policies/reports-auditor-role-trust-policy.json`](policies/reports-auditor-role-trust-policy.json)
   (Principal = `bob`). Name it `reports-auditor-role`. Attach the permission policy
   `S3ReportsReadOnly` (reused from Part 1).
   - Trust policy = **who may assume** (WHO). Permission policy = **what it can do** (WHAT).

**Verify:**

| # | Action | Expected |
|---|--------|----------|
| 1 | As `bob` directly, access S3 | ❌ Deny |
| 2 | `bob` **switches role** into `reports-auditor-role`, reads `reports/hello.txt` | ✅ Allow |

*(Hardening: a real cross‑account trust policy would also require `sts:ExternalId` and/or
`aws:MultiFactorAuthPresent` — testable via `aws sts assume-role`.)*

## Part 3 — Permissions boundary (a ceiling an admin grant can't cross)

**Goal:** user `carol` has `AdministratorAccess`, but a boundary caps her to S3/CloudWatch only.

1. **Boundary policy:** IAM → Policies → Create policy → JSON →
   [`policies/boundary-s3-cw-only.json`](policies/boundary-s3-cw-only.json)
   (allow `s3:*`, `cloudwatch:*`, `logs:*`). Name it `boundary-s3-cw-only`.
2. **User `carol`:** create the user → attach the managed policy **AdministratorAccess** →
   set **Permissions boundary = `boundary-s3-cw-only`**.
   - Effective permissions = identity policy ∩ boundary = S3/CloudWatch only.

**Verify (IAM Policy Simulator):**

| # | Action simulated | Expected |
|---|------------------|----------|
| 1 | `ec2:DescribeInstances` | ❌ Implicitly denied by the permissions boundary |
| 2 | `s3:*` | ✅ Allowed |

## Infrastructure as Code (CloudFormation)
The whole lab (bucket, managed policy, group, role, boundary, 3 users) is codified in
[`cloudformation/template.yaml`](cloudformation/template.yaml) — all 8 resources with the
right attachments. Deploy / tear down:
```bash
aws cloudformation deploy \
  --stack-name project1-iam-least-privilege \
  --template-file cloudformation/template.yaml \
  --parameter-overrides BucketName=<globally-unique-name> \
  --capabilities CAPABILITY_NAMED_IAM

aws cloudformation delete-stack --stack-name project1-iam-least-privilege
```
`CAPABILITY_NAMED_IAM` is required because the template creates named IAM resources.

## Security scanning
```bash
cfn-lint cloudformation/template.yaml
python -m checkov.main -f cloudformation/template.yaml
```
Fixed: S3 bucket versioning. Kept intentionally: the `boundary-s3-cw-only` wildcard is a
**permissions boundary** (caps the maximum; never grants) — Checkov's wildcard flag is a
false positive here. See the README for the full reasoning.

## Cleanup
Delete the 3 users, the group, the role, the customer‑managed policies and the bucket
(empty it first). No credentials are stored in this repo.

---

*Part of [aws-security-projects](../README.md).*
