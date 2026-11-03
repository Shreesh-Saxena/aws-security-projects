import os
import json
import time
import boto3
from datetime import datetime, timezone

ec2 = boto3.client('ec2')
sns = boto3.client('sns')

ISOLATION_SG = os.environ['ISOLATION_SG']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']


def lambda_handler(event, context):
    print("Received event:", json.dumps(event))
    detail = event.get('detail', {})
    finding_type = detail.get('type', 'Unknown')
    severity = detail.get('severity', 'N/A')
    title = detail.get('title', '')
    finding_id = detail.get('id', '')

    instance_id = (detail.get('resource', {})
                        .get('instanceDetails', {})
                        .get('instanceId'))

    if not instance_id:
        print("No EC2 instance in this finding; nothing to isolate.")
        return {"status": "skipped", "reason": "no instanceId in finding"}

    # Describe the instance once (used for the idempotency check and for the volumes).
    try:
        inst = ec2.describe_instances(InstanceIds=[instance_id])['Reservations'][0]['Instances'][0]
    except Exception as e:
        print("Describe error:", e)
        return {"status": "error", "reason": str(e)}

    # Idempotency: GuardDuty can emit the same finding several times, which would invoke
    # this function repeatedly and race CreateSnapshot on the same volume
    # (SnapshotCreationPerVolumeRateExceeded). If already isolated, stop here.
    existing_tags = {t['Key']: t['Value'] for t in inst.get('Tags', [])}
    if existing_tags.get('Status') == 'ISOLATED':
        print(f"Instance {instance_id} already isolated; skipping duplicate event.")
        return {"status": "already_isolated", "instance": instance_id}

    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    actions = []

    # 1) ISOLATE: replace the instance's security groups with the isolation SG
    try:
        ec2.modify_instance_attribute(InstanceId=instance_id, Groups=[ISOLATION_SG])
        actions.append(f"Replaced security groups with isolation SG {ISOLATION_SG}")
    except Exception as e:
        actions.append(f"ISOLATION FAILED: {e}")
        print("Isolation error:", e)

    # 2) FORENSICS: snapshot every attached EBS volume (small retry for transient throttling)
    snapshot_ids = []
    for bdm in inst.get('BlockDeviceMappings', []):
        vol_id = bdm.get('Ebs', {}).get('VolumeId')
        if not vol_id:
            continue
        for attempt in range(3):
            try:
                snap = ec2.create_snapshot(
                    VolumeId=vol_id,
                    Description=f"Forensic snapshot of {vol_id} from {instance_id} ({finding_type})",
                    TagSpecifications=[{
                        'ResourceType': 'snapshot',
                        'Tags': [
                            {'Key': 'Name', 'Value': f'forensic-{instance_id}'},
                            {'Key': 'SourceInstance', 'Value': instance_id},
                            {'Key': 'GuardDutyFinding', 'Value': finding_type},
                        ]
                    }]
                )
                snapshot_ids.append(snap['SnapshotId'])
                break
            except Exception as e:
                if 'RateExceeded' in str(e) and attempt < 2:
                    time.sleep(2 * (attempt + 1))  # back off and retry
                    continue
                actions.append(f"SNAPSHOT FAILED for {vol_id}: {e}")
                print("Snapshot error:", e)
                break
    if snapshot_ids:
        actions.append(f"Created forensic snapshot(s): {', '.join(snapshot_ids)}")

    # 3) TAG the instance as quarantined
    try:
        ec2.create_tags(Resources=[instance_id], Tags=[
            {'Key': 'Status', 'Value': 'ISOLATED'},
            {'Key': 'IsolatedBy', 'Value': 'guardduty-auto-response'},
            {'Key': 'IsolatedAt', 'Value': now},
            {'Key': 'GuardDutyFinding', 'Value': finding_type},
        ])
        actions.append("Tagged instance Status=ISOLATED")
    except Exception as e:
        actions.append(f"TAGGING FAILED: {e}")
        print("Tagging error:", e)

    # 4) NOTIFY via SNS
    message = (
        "GuardDuty auto-isolation triggered\n\n"
        f"Instance:   {instance_id}\n"
        f"Finding:    {finding_type}\n"
        f"Severity:   {severity}\n"
        f"Title:      {title}\n"
        f"Finding ID: {finding_id}\n"
        f"Time (UTC): {now}\n\n"
        "Actions taken:\n- " + "\n- ".join(actions)
    )
    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"[SECURITY] EC2 {instance_id} auto-isolated by GuardDuty",
            Message=message
        )
    except Exception as e:
        print("SNS publish error:", e)

    print(message)
    return {"status": "isolated", "instance": instance_id,
            "snapshots": snapshot_ids, "actions": actions}
