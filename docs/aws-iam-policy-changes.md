# CareerLift AI — Required IAM Policy Changes (for administrator review)

Status: **PROPOSAL ONLY.** Kiro made no IAM changes, created no resources, attached no policies, created
no keys, invoked no Bedrock, deployed nothing. These are the exact documents an AWS administrator applies.

## Context (verified)
- Account: **074095960941** · Region: **us-east-1**
- SSO profile: `career-lift` · Permission set: **CareerLiftDeveloperAccess** · Policy to extend:
  **CareerLiftAI-AWS-Developer-Policy**
- Authenticated identity confirmed; the blocker is that the developer policy currently grants none of the
  needed actions.
- Approved security model: a **dedicated EC2 instance role** holds the application's runtime permissions;
  the **developer permission set** receives infrastructure permissions + **`iam:PassRole` scoped to only
  that one role** (no unrestricted PassRole, no AdministratorAccess).

Placeholders used below — replace before applying:
- `ACCOUNT_ID` = `074095960941`
- `INSTANCE_ROLE_NAME` = `CareerLiftAppInstanceRole` (the dedicated EC2 role the admin creates)
- `REGION` = `us-east-1`

---

## PART A — ADMINISTRATOR-ONLY actions (not granted to the developer)

These are privileged, one-time actions an admin performs. They are deliberately **kept out** of the
developer permission set.

### A1. Create the dedicated EC2 instance role + instance profile
Role name: `CareerLiftAppInstanceRole`. Trust policy (who may assume it — the EC2 service only):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "ec2.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```
Then create an instance profile of the same name and add the role to it (EC2 attaches a role via its
instance profile):
- `aws iam create-role --role-name CareerLiftAppInstanceRole --assume-role-policy-document file://trust.json`
- `aws iam create-instance-profile --instance-profile-name CareerLiftAppInstanceRole`
- `aws iam add-role-to-instance-profile --instance-profile-name CareerLiftAppInstanceRole --role-name CareerLiftAppInstanceRole`

### A2. Attach the application runtime policy (PART B) to that role.

### A3. Enable Bedrock model access for Amazon Nova 2 Lite
In the Bedrock console (us-east-1) → **Model access** → request/enable access to **Amazon Nova 2 Lite**
(`amazon.nova-2-lite-v1:0`). IAM permission alone does not grant model access; this account-level opt-in
is required and is an admin action.

### A4. (If used) Create the SSM SecureString + its KMS key
Create `/careerlift/auth_pepper` (SecureString). If a customer-managed KMS key is used, note its ARN for
PART B/C `kms:Decrypt`.

**Why admin-only:** `iam:CreateRole`, `iam:CreateInstanceProfile`, `iam:AttachRolePolicy`, and Bedrock
model-access enablement are privilege-escalation-sensitive. Granting them to a developer identity would
let it mint arbitrary roles — so they stay with the admin, and the developer only gets `PassRole` on the
single finished role.

---

## PART B — INSTANCE ROLE policy (attached by admin to `CareerLiftAppInstanceRole`)

This is what the **running application** can do. Least-privilege: Bedrock inference on the Nova ARNs only,
Translate, its own CloudWatch log group, and read of its own SSM parameter. No EC2/IAM/S3 management.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockNovaInference",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-2-lite-v1:0",
        "arn:aws:bedrock:us-east-1:074095960941:inference-profile/us.amazon.nova-2-lite-v1:0",
        "arn:aws:bedrock:*::foundation-model/amazon.nova-2-lite-v1:0"
      ]
    },
    {
      "Sid": "BedrockReadOnlyDiscovery",
      "Effect": "Allow",
      "Action": [
        "bedrock:GetFoundationModel",
        "bedrock:GetInferenceProfile"
      ],
      "Resource": "*"
    },
    {
      "Sid": "TranslateFeedback",
      "Effect": "Allow",
      "Action": [ "translate:TranslateText" ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchLogsOwnGroup",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogStreams"
      ],
      "Resource": "arn:aws:logs:us-east-1:074095960941:log-group:/careerlift/*:*"
    },
    {
      "Sid": "CloudWatchLogsCreateGroup",
      "Effect": "Allow",
      "Action": [ "logs:CreateLogGroup" ],
      "Resource": "arn:aws:logs:us-east-1:074095960941:log-group:/careerlift/*"
    },
    {
      "Sid": "CloudWatchMetricsPush",
      "Effect": "Allow",
      "Action": [ "cloudwatch:PutMetricData" ],
      "Resource": "*",
      "Condition": { "StringEquals": { "cloudwatch:namespace": "CareerLift" } }
    },
    {
      "Sid": "ReadAuthPepperParam",
      "Effect": "Allow",
      "Action": [ "ssm:GetParameter", "ssm:GetParameters" ],
      "Resource": "arn:aws:ssm:us-east-1:074095960941:parameter/careerlift/*"
    }
  ]
}
```
> Notes: `bedrock:Get*` and `cloudwatch:PutMetricData` do not support resource-level ARNs for these
> actions, so they use `"*"` (narrowed by the namespace condition where possible). If `/careerlift/auth_pepper`
> is a SecureString under a **customer-managed** KMS key, add a `kms:Decrypt` statement scoped to that key ARN:
```json
    {
      "Sid": "DecryptAuthPepper",
      "Effect": "Allow",
      "Action": [ "kms:Decrypt" ],
      "Resource": "arn:aws:kms:us-east-1:074095960941:key/REPLACE-WITH-KEY-ID"
    }
```
> (Not needed if the parameter uses the AWS-managed `aws/ssm` key, which `ssm:GetParameter` can decrypt
> implicitly for the account.)

---

## PART C — DEVELOPER permission-set policy additions
Add these statements to **CareerLiftAI-AWS-Developer-Policy** (the policy on the CareerLiftDeveloperAccess
permission set). This lets the developer provision and operate the infra and **pass only the one dedicated
role** — but NOT create roles, NOT pass any other role, NOT administer IAM.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Ec2DescribeReadOnly",
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*",
        "ec2:GetConsoleOutput"
      ],
      "Resource": "*"
    },
    {
      "Sid": "Ec2ProvisionAndOperate",
      "Effect": "Allow",
      "Action": [
        "ec2:RunInstances",
        "ec2:StartInstances",
        "ec2:StopInstances",
        "ec2:RebootInstances",
        "ec2:TerminateInstances",
        "ec2:CreateTags",
        "ec2:CreateVolume",
        "ec2:AttachVolume",
        "ec2:DetachVolume",
        "ec2:DeleteVolume",
        "ec2:CreateSnapshot",
        "ec2:AllocateAddress",
        "ec2:AssociateAddress",
        "ec2:DisassociateAddress",
        "ec2:ReleaseAddress"
      ],
      "Resource": "*",
      "Condition": { "StringEquals": { "aws:RequestedRegion": "us-east-1" } }
    },
    {
      "Sid": "SecurityGroupManagement",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateSecurityGroup",
        "ec2:DeleteSecurityGroup",
        "ec2:AuthorizeSecurityGroupIngress",
        "ec2:AuthorizeSecurityGroupEgress",
        "ec2:RevokeSecurityGroupIngress",
        "ec2:RevokeSecurityGroupEgress"
      ],
      "Resource": "*",
      "Condition": { "StringEquals": { "aws:RequestedRegion": "us-east-1" } }
    },
    {
      "Sid": "PassOnlyTheDedicatedInstanceRole",
      "Effect": "Allow",
      "Action": [ "iam:PassRole" ],
      "Resource": "arn:aws:iam::074095960941:role/CareerLiftAppInstanceRole",
      "Condition": { "StringEquals": { "iam:PassedToService": "ec2.amazonaws.com" } }
    },
    {
      "Sid": "AssociateInstanceProfileOnly",
      "Effect": "Allow",
      "Action": [
        "ec2:AssociateIamInstanceProfile",
        "ec2:ReplaceIamInstanceProfileAssociation",
        "ec2:DisassociateIamInstanceProfile",
        "iam:ListInstanceProfiles",
        "iam:ListInstanceProfilesForRole",
        "iam:GetInstanceProfile",
        "iam:GetRole",
        "iam:ListRoles"
      ],
      "Resource": "*"
    },
    {
      "Sid": "BedrockDiscoveryAndInferenceForDev",
      "Effect": "Allow",
      "Action": [
        "bedrock:ListFoundationModels",
        "bedrock:GetFoundationModel",
        "bedrock:ListInferenceProfiles",
        "bedrock:GetInferenceProfile",
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "*",
        "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-2-lite-v1:0",
        "arn:aws:bedrock:us-east-1:074095960941:inference-profile/us.amazon.nova-2-lite-v1:0"
      ]
    },
    {
      "Sid": "CloudWatchAndLogs",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:DescribeAlarms",
        "cloudwatch:PutMetricAlarm",
        "cloudwatch:DeleteAlarms",
        "cloudwatch:GetMetricData",
        "cloudwatch:ListMetrics",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:GetLogEvents",
        "logs:FilterLogEvents",
        "logs:CreateLogGroup"
      ],
      "Resource": "*",
      "Condition": { "StringEquals": { "aws:RequestedRegion": "us-east-1" } }
    },
    {
      "Sid": "SsmParameterStoreCareerLift",
      "Effect": "Allow",
      "Action": [
        "ssm:DescribeParameters",
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:PutParameter"
      ],
      "Resource": "arn:aws:ssm:us-east-1:074095960941:parameter/careerlift/*"
    },
    {
      "Sid": "CostAndBillingVisibility",
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "ce:GetCostForecast",
        "budgets:ViewBudget",
        "budgets:DescribeBudgets"
      ],
      "Resource": "*"
    }
  ]
}
```

### Important caveats on PART C
- **`iam:PassRole` is scoped to exactly one role ARN** (`CareerLiftAppInstanceRole`) and conditioned to
  `ec2.amazonaws.com`. This is the opposite of unrestricted PassRole: the developer can attach only this
  prepared role, only to EC2. This is what makes "create the role as admin, pass it as developer" safe.
- **No role creation for the developer.** `iam:CreateRole` / `CreateInstanceProfile` / `AttachRolePolicy`
  are intentionally absent — those stay in PART A (admin).
- **`budgets:*` / Cost Explorer** are account-level and may be managed in the management account; if this
  member account can't see billing, that statement will simply return empty — harmless. Billing data
  visibility may also require the account's "IAM access to Billing" setting enabled by an admin.
- **Region guard:** most provisioning statements are conditioned to `us-east-1` so this identity can't
  spin up resources elsewhere. `ec2:Describe*`, `iam:*` reads, and `bedrock:Get*` don't support that
  condition cleanly, so they're left unconditioned (read-only or global by nature).
- **Deliberately excluded (tighten later if desired):** `ec2:DeleteSecurityGroup` and
  `ec2:TerminateInstances`/`DeleteVolume` are included for teardown; remove them if you want a
  provision-only (no-destroy) developer. Nothing here grants S3 or RDS (not needed per the architecture
  plan).

---

## PART D — Exactly what the administrator must do in IAM Identity Center

1. **Create the instance role + profile** (PART A1) in account `074095960941`.
2. **Attach PART B** as an inline or managed policy to `CareerLiftAppInstanceRole`.
3. **Enable Bedrock model access** for Amazon Nova 2 Lite in us-east-1 (PART A3).
4. **(If using SSM SecureString)** create `/careerlift/auth_pepper` and note the KMS key (PART A4).
5. **Edit the developer permission set:** in IAM Identity Center → Permission sets →
   **CareerLiftDeveloperAccess** → its inline/customer policy **CareerLiftAI-AWS-Developer-Policy** →
   merge in the PART C statements (replace `ACCOUNT_ID`/role name if changed).
6. **Re-provision the permission set** to the assigned account (Identity Center requires re-provisioning
   after a permission-set policy edit for it to take effect on the account's generated role).
7. Tell the developer to **re-authenticate** (`aws sso login --profile career-lift`) so the new session
   picks up the updated permissions, then Kiro will re-run the read-only readiness probes to confirm.

### Verification after the admin applies changes (Kiro will run — all read-only)
- `aws sts get-caller-identity` (identity unchanged)
- `aws ec2 describe-instances` / `describe-vpcs` (should now succeed)
- `aws ec2 run-instances … --dry-run` (expects `DryRunOperation` = allowed, still creates nothing)
- `aws iam get-role --role-name CareerLiftAppInstanceRole` (role exists)
- `aws bedrock list-foundation-models` + `get-foundation-model --model-identifier amazon.nova-2-lite-v1:0`
  (discovery works; **model is NOT invoked**)
- `aws ce get-cost-and-usage …` (billing visibility, if enabled)

---

## Summary: admin vs developer split

| Capability | Admin (one-time) | Developer permission set |
|---|---|---|
| Create instance role + profile | ✅ PART A1 | ❌ |
| Attach runtime policy to the role | ✅ PART A2/B | ❌ |
| Enable Bedrock Nova model access | ✅ PART A3 | ❌ |
| Create SSM SecureString / KMS | ✅ PART A4 | writes under `/careerlift/*` only (PART C) |
| EC2/EBS/SG provision + operate (us-east-1) | — | ✅ PART C |
| `iam:PassRole` | — | ✅ **only** `CareerLiftAppInstanceRole` → ec2 |
| Bedrock discovery + inference | (role gets runtime) | ✅ PART C (for testing) |
| CloudWatch/Logs, SSM `/careerlift/*`, cost visibility | — | ✅ PART C |
| CreateRole / AttachRolePolicy / AdministratorAccess | kept with admin | ❌ never granted |

No access keys anywhere (SSO + instance role only). Nothing was applied by Kiro.
