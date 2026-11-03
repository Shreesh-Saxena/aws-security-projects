# BUILD — Project 3: GuardDuty Automated Incident Response

A complete, reproducible step‑by‑step runbook. Everything was first built by hand in the
**console** (for the screenshots) in **us‑east‑1**, then verified with a **real** GuardDuty
finding. Replace the placeholder account id `111122223333` and the resource IDs below with
your own.

> **Cost:** GuardDuty is free for 30 days (per account/region). The EC2 instance and the EBS
> snapshot cost a little — tear everything down when done (see the end).

---

## Prerequisites
- An AWS account where GuardDuty is available (I used a dedicated sandbox account).
- Console access as an admin user (all the build is done in the browser).
- Region **us‑east‑1** (N. Virginia) throughout — GuardDuty is regional, keep everything in one region.

---

## Step 1 — Enable GuardDuty
1. Console → search **GuardDuty** → open it (confirm region = **us‑east‑1** top‑right).
2. **Get started** → keep **Enable all GuardDuty features** selected → **Enable GuardDuty**.
3. The Summary/Findings dashboard appears (findings empty — normal). GuardDuty now reads
   CloudTrail, VPC flow and **DNS query** logs automatically (agentless — you don't enable
   Flow Logs or DNS logging yourself).

## Step 2 — Launch the "victim" EC2
1. EC2 → **Launch instances**.
2. Name `guardduty-victim-test`; AMI **Amazon Linux 2023**; type `t3.micro`.
3. Create a key pair (`guardduty-test-key`, RSA, .pem) — download it.
4. Network: default VPC, **Auto‑assign public IP = Enable**. Create security group `victim-sg`
   with inbound **SSH 22 from My IP**.
   > **Heads‑up (we hit this):** EC2 Instance Connect (the browser "Connect") comes from
   > **AWS's** servers, not your IP — so "SSH from My IP" alone makes it fail with *"Failed to
   > connect / unable to connect"*. If you plan to connect that way (Step 8), also add a second
   > inbound rule now: **SSH 22 from `18.206.107.24/29`** (the us‑east‑1 EC2 Instance Connect
   > range). You can add it later in Step 8 instead, but adding it here avoids the error.
5. Storage default (8 GiB). **Launch instance**. Wait for **Running** + 3/3 checks.
6. Note the **Instance ID** (e.g. `i-0cbcada1e4c53fb7b`) and VPC id.

## Step 3 — Isolation security group (the quarantine)
1. EC2 → **Security Groups** → **Create security group**.
2. Name `forensic-isolation-sg`; **VPC = the same default VPC** as the instance.
3. **Inbound rules:** none. **Outbound rules:** delete the default `All traffic → 0.0.0.0/0`
   rule so there are **0 inbound and 0 outbound** rules.
4. Create. Note its **SG ID** (e.g. `sg-08eb2b53e02a53d99`). With no rules, an instance moved
   into this SG can talk to nothing — full network isolation.

## Step 4 — IAM role for the Lambda
1. IAM → **Roles** → **Create role** → trusted entity **AWS service → Lambda**.
2. Attach **AWSLambdaBasicExecutionRole** (for CloudWatch Logs). Name the role
   `guardduty-isolation-lambda-role`. Create.
3. Open the role → **Add permissions → Create inline policy → JSON** → paste
   [`policies/isolation-ec2-sns-policy.json`](policies/isolation-ec2-sns-policy.json)
   (EC2 describe/modify/snapshot/tag + `sns:Publish`). Name it `isolation-ec2-sns-policy`.
   The role now has 2 policies.

## Step 5 — SNS topic + email subscription
1. SNS → **Topics** → **Create topic** → **Standard**, name `guardduty-isolation-alerts`.
   Note the **Topic ARN** (`arn:aws:sns:us-east-1:111122223333:guardduty-isolation-alerts`).
2. **Create subscription** → Protocol **Email** → your address → Create.
3. Open the confirmation email → **Confirm subscription** (status becomes *Confirmed*).

## Step 6 — Lambda function
1. Lambda → **Create function** → **Author from scratch**, name `guardduty-auto-isolation`,
   runtime **Python 3.13**.
2. Permissions → **Use an existing role** → `guardduty-isolation-lambda-role`. Create.
3. **Code** tab → paste [`lambda/lambda_function.py`](lambda/lambda_function.py) → **Deploy**.
4. **Configuration → Environment variables** → add:
   - `ISOLATION_SG` = your isolation SG id (`sg-08eb2b53e02a53d99`)
   - `SNS_TOPIC_ARN` = your topic ARN
5. **Configuration → General configuration** → **Timeout = 30 sec** (default 3s is too short).

The function: reads the finding's `instanceId` → replaces the instance's SGs with the
isolation SG → snapshots each EBS volume → tags the instance `Status=ISOLATED` → publishes SNS.

## Step 7 — EventBridge rule (finding → Lambda)
1. EventBridge → **Rules** → **Create rule** (Advanced builder) → name
   `guardduty-finding-to-isolation`, event bus `default`, type *Rule with an event pattern*.
2. Event pattern (AWS services → GuardDuty → GuardDuty Finding):
   ```json
   { "source": ["aws.guardduty"], "detail-type": ["GuardDuty Finding"] }
   ```
3. Target: **Lambda function → `guardduty-auto-isolation`**. Create. (EventBridge adds the
   invoke permission automatically.)

## Step 8 — Test with a REAL finding
Sample findings use **fake** instance IDs, so they can't prove real isolation. Instead,
generate a real finding from the real instance using GuardDuty's official test domain.

1. **Connect** to the instance: EC2 → Instances → `guardduty-victim-test` → **Connect →
   EC2 Instance Connect**. If it fails ("unable to connect"), add an inbound rule to
   `victim-sg`: **SSH 22 from `18.206.107.24/29`** (the us‑east‑1 EC2 Instance Connect range),
   then connect again.
2. In the instance terminal, resolve the test C2 domain a few times:
   ```bash
   for i in $(seq 1 30); do curl -s http://guarddutyc2activityb.com/ -o /dev/null; getent hosts guarddutyc2activityb.com; sleep 2; done
   ```
   (`guarddutyc2activityb.com` is an AWS test domain on GuardDuty's threat list — harmless; it
   just triggers the finding `Backdoor:EC2/C&CActivity.B!DNS`.)
3. Watch **GuardDuty → Findings** (the DNS finding takes ~10–15 min). When it appears, the
   pipeline fires automatically. Verify:
   - GuardDuty shows `Backdoor:EC2/C&CActivity.B!DNS` (High) on your instance.
   - EC2 → instance → **Security** tab: SG is now `forensic-isolation-sg`.
   - EC2 → instance → **Tags**: `Status=ISOLATED` (+ IsolatedBy / IsolatedAt / GuardDutyFinding).
   - EC2 → **Snapshots**: a `forensic-i-...` snapshot.
   - Your email: `[SECURITY] EC2 ... auto-isolated by GuardDuty`.
   - Lambda → **Monitor → View CloudWatch logs**: the "Actions taken" list.

## A real bug (and the fix)
On the live run the snapshot step failed with `SnapshotCreationPerVolumeRateExceeded` —
GuardDuty emitted the same finding several times (`count` 2→4), so the Lambda ran repeatedly
and raced `CreateSnapshot` on the same volume. **Fix:** an idempotency guard (return early if
the instance is already tagged `Status=ISOLATED`) plus a short retry/back‑off on `CreateSnapshot`.
Both are in [`lambda/lambda_function.py`](lambda/lambda_function.py).

## Cleanup (tear everything down)
Via console, or with the CLI:
```bash
# cost resources
aws ec2 terminate-instances --instance-ids <instance-id> --region us-east-1
aws ec2 delete-snapshot --snapshot-id <snap-id> --region us-east-1

# the pipeline (free, but clean it up)
TID=$(aws events list-targets-by-rule --rule guardduty-finding-to-isolation --query "Targets[0].Id" --output text --region us-east-1)
aws events remove-targets --rule guardduty-finding-to-isolation --ids "$TID" --region us-east-1
aws events delete-rule --name guardduty-finding-to-isolation --region us-east-1
aws lambda delete-function --function-name guardduty-auto-isolation --region us-east-1
aws sns delete-topic --topic-arn <topic-arn> --region us-east-1
aws iam delete-role-policy --role-name guardduty-isolation-lambda-role --policy-name isolation-ec2-sns-policy
aws iam detach-role-policy --role-name guardduty-isolation-lambda-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam delete-role --role-name guardduty-isolation-lambda-role
aws ec2 delete-security-group --group-id <isolation-sg-id> --region us-east-1   # after instance is terminated
aws ec2 delete-security-group --group-id <victim-sg-id> --region us-east-1

# GuardDuty: suspend (reusable) or disable
aws guardduty update-detector --detector-id <detector-id> --no-enable --region us-east-1
```

---

*Phase 2 (Terraform) will codify this same stack — see the roadmap in [`README.md`](README.md).*
