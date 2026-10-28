# AWS Security Projects

Hands-on AWS security labs I build to learn by doing and to prepare for the
**AWS Certified Security – Specialty (SCS-C03)** exam. Each project takes one
realistic scenario, implements it with least privilege, and **verifies it** —
proving that the allowed path works and everything else is denied.

Each project is self-contained and includes:
- a **README** with the scenario, the design decisions, and the verification results
- the **policies / templates** used
- **screenshots** of the allowed and denied cases (proof it actually works)
- **Infrastructure as Code** (CloudFormation or Terraform) so the setup is reproducible

## Projects

| # | Project | Focus area | IaC | Status |
|---|---------|------------|-----|--------|
| 01 | [IAM Least-Privilege Access to S3](01-iam-least-privilege) | Identity & Access | CloudFormation | ✅ Core complete |
| 02 | [Secure VPC (three-tier: web / app / db)](02-secure-vpc) | Network | CloudFormation | ✅ Core complete |
| 03 | GuardDuty → EventBridge → Lambda auto-response | Detection & Response | Terraform | ⬜ Planned |
| 04 | S3 Data Protection (Block Public Access, SSE-KMS, bucket policy) | Data Protection | Terraform | ⬜ Planned |
| 05 | Multi-account guardrails (SCP / RCP, AWS Organizations) | Governance | Terraform | ⬜ Planned |

## Approach

Projects map to the SCS-C03 domains and to how security works in layers —
**identity → network → detection → data → governance**. Every lab is built and
tested in a personal AWS account, then the test resources are deleted (no ongoing
cost, no credentials stored in this repository).

## Author

**Shreesh Saxena** — studying for AWS Security – Specialty, building a hands-on
cloud security portfolio.
