# Project 1 — IAM Least-Privilege Access to S3

A hands-on demonstration of the **principle of least privilege**: an IAM user is
granted *just enough* permission to read one folder in one S3 bucket — and nothing
more. Every other action (listing the account's buckets, reading files outside that
folder, uploading) is denied, and I verified each case in the AWS Console.

> **Why this matters:** Over-permissive IAM policies are one of the most common causes
> of cloud data exposure. This project shows how a tightly scoped, condition-based
> policy limits the "blast radius" if a user's credentials are ever compromised.

---

## Scenario

An auditor (`Alice`) needs **read-only** access to audit reports stored under the
`reports/` prefix of an S3 bucket. She must **not** be able to:

- list all buckets in the account,
- read files stored outside `reports/` (e.g. `secret.txt` in the bucket root),
- upload, modify, or delete anything.

## Architecture

```
IAM user: Alice
   └── member of group: reports-readers
          └── attached policy: S3ReportsReadOnly  (customer managed)
                 ├── s3:ListBucket   on the bucket   (ONLY when prefix = reports/*)
                 └── s3:GetObject    on bucket/reports/*
```

Permissions are attached to the **group**, not the user directly — so adding more
auditors later means just adding them to the group.

## The policy

See [`policies/S3ReportsReadOnly.json`](policies/S3ReportsReadOnly.json).

Two design decisions make this least-privilege:

1. **`ListBucket` is gated by a condition** — `s3:prefix` must match `reports/*`.
   Listing the bucket root (no prefix) is therefore denied.
2. **`GetObject` is scoped to `reports/*`** — object permissions use the object ARN
   with `/reports/*`, so files elsewhere in the bucket cannot be read.

```json
"Condition": {
  "StringLike": { "s3:prefix": "reports/*" }
}
```

## Steps performed

1. Created S3 bucket `shreesh-iam-least-privilege` (Block Public Access ON).
2. Added two objects: `reports/hello.txt` (allowed) and `secret.txt` in the root (off-limits).
3. Created the customer-managed policy `S3ReportsReadOnly` (above).
4. Created group `reports-readers` and attached the policy.
5. Created IAM user `Alice` with console access, added to the group.
6. Signed in as `Alice` in a separate (incognito) session and tested each case.

## Verification

| # | Action attempted | Expected | Result |
|---|------------------|----------|--------|
| 1 | Download `reports/hello.txt` | Allow | ✅ Completed (5 bytes) |
| 2 | List all buckets in the account | Deny | ❌ `s3:ListAllMyBuckets` denied |
| 3 | List the bucket **root** (no prefix) | Deny | ❌ `s3:ListBucket` denied by prefix condition |
| 4 | Upload `one.txt` to `reports/` | Deny | ❌ Access denied (no write permission) |
| 5 | Open `secret.txt` (outside `reports/`) | Deny | ❌ No permission to get object |

Screenshots for each case are in [`screenshots/`](screenshots/).

**Allowed — `reports/hello.txt` is listed and downloads successfully:**

![reports folder visible](screenshots/1a-reports-folder-visible.png)
![hello.txt downloaded](screenshots/1b-hello-txt-downloaded.png)

**Denied — listing all buckets, and listing the bucket root:**

![list all buckets denied](screenshots/2-list-all-buckets-denied.png)
![bucket root list denied](screenshots/3-bucket-root-list-denied.png)

**Denied — uploading to `reports/`, and reading `secret.txt` outside `reports/`:**

![upload access denied](screenshots/4-upload-access-denied.png)
![secret.txt denied](screenshots/5-secret-txt-denied.png)

## Key takeaways

- **Deny by default.** IAM grants nothing until you explicitly allow it; everything
  not allowed is already denied.
- **Conditions shrink scope further.** The `s3:prefix` condition means even a granted
  `ListBucket` only works for the intended folder.
- **Object-level ARNs matter.** `GetObject` on `bucket/reports/*` does not extend to
  `bucket/secret.txt`.
- **Attach permissions to groups**, not individual users, for maintainability.

## Cleanup

To avoid lingering resources, after documenting the project I deleted the IAM user,
the group, the policy, and the S3 bucket. No credentials or access keys are stored in
this repository.

---

*Part of [aws-security-projects](../README.md) — hands-on labs for AWS Security.*
