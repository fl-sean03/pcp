---
name: self-improvement
description: PCP's autonomous capability acquisition system - detect, assess, and acquire missing capabilities
triggers:
  - can't do
  - don't know how
  - missing capability
  - need a tool
  - install
  - capability gap
  - self-improve
  - acquire capability
  - missing module
  - command not found
---

# Self-Improvement System

## Purpose

This skill enables PCP to autonomously detect and acquire missing capabilities. When you encounter something you can't do (missing package, tool, or integration), use this system to:

1. **Detect** what capability is missing
2. **Assess** the risk of acquiring it
3. **Acquire** the capability (or ask user if needed)
4. **Create** a reusable skill for future use

## When to Use

Use this system when:
- An import fails (`ModuleNotFoundError`, `ImportError`)
- A CLI tool is missing (`command not found`)
- A service integration is needed (Slack, Notion, Jira, etc.)
- Cloud provider access is required (AWS, GCP, Oracle)
- Any task fails due to missing capability

## Core API

### Detecting Capability Gaps

```python
from self_improvement import detect_capability_gap, CapabilityGapError

# From error message
gap = detect_capability_gap(
    task_description="Transcribe audio file",
    error_message="ModuleNotFoundError: No module named 'whisper'",
    file_path="/path/to/audio.mp3"
)

if gap:
    print(f"Gap detected: {gap.gap_description}")
    print(f"Type: {gap.gap_type}")
    print(f"Solutions: {gap.suggested_solutions}")
```

### Assessing Risk

```python
from self_improvement import assess_risk, RiskLevel

assessment = assess_risk(gap)

print(f"Risk Level: {assessment.level}")  # LOW, MEDIUM, HIGH, CRITICAL
print(f"Score: {assessment.score}")        # 0.0 to 1.0
print(f"Requires Approval: {assessment.requires_approval}")
print(f"Requires Credentials: {assessment.requires_credentials}")
```

### Risk Levels and Actions

| Level | Score | Action |
|-------|-------|--------|
| LOW | 0.0-0.25 | Auto-acquire |
| MEDIUM | 0.25-0.50 | Acquire + notify |
| HIGH | 0.50-0.75 | Ask first |
| CRITICAL | 0.75-1.0 | Explicit approval |

### Acquiring Capabilities

```python
from self_improvement import acquire_capability

# Automatic acquisition (for low/medium risk)
result = acquire_capability(gap)

if result.success:
    print(f"Acquired via: {result.method}")
    print(f"Skill created: {result.skill_created}")
else:
    if result.user_action_required:
        # Need to ask user
        print(f"User input needed: {result.user_action_required}")
    else:
        print(f"Failed: {result.error}")
```

### With User Credentials

```python
# For service integrations requiring API keys
result = acquire_capability(
    gap,
    credentials={
        "SLACK_BOT_TOKEN": "xoxb-..."
    }
)
```

## Self-Improving Task Execution

Wrap any function to automatically handle capability gaps:

```python
from self_improvement import execute_with_self_improvement

def transcribe_audio(path):
    import whisper  # May not be installed
    model = whisper.load_model("base")
    return model.transcribe(path)

# This will:
# 1. Try to run the function
# 2. Detect the missing whisper package
# 3. Install it automatically (low risk)
# 4. Retry the function
result = execute_with_self_improvement(
    transcribe_audio,
    "/path/to/audio.mp3",
    task_description="Transcribe audio file"
)
```

### Using the Decorator

```python
from self_improvement import self_improving

@self_improving(task_description="Process video files")
def extract_audio(video_path):
    import subprocess
    subprocess.run(["ffmpeg", "-i", video_path, "output.mp3"], check=True)

# If ffmpeg is missing, it will be installed automatically
extract_audio("/path/to/video.mp4")
```

## Explicitly Raising Gaps

When you detect a missing capability proactively:

```python
from self_improvement import raise_capability_gap

def send_to_slack(channel, message):
    import os
    if not os.environ.get("SLACK_BOT_TOKEN"):
        raise_capability_gap(
            gap_type="service_integration",
            description="Slack API access",
            task="Send Slack message",
            pattern="slack_integration"  # Uses predefined pattern
        )

    # ... proceed with Slack API
```

## Known Capability Patterns

The system has built-in patterns for common capabilities:

### File Processing
- `audio_transcription` - Whisper for audio files
- `video_processing` - FFmpeg for video files

### Service Integrations
- `notion_integration` - Notion API
- `slack_integration` - Slack API
- `jira_integration` - Jira/Atlassian

### Cloud Providers
- `aws_access` - AWS (boto3, credentials)
- `gcp_access` - Google Cloud
- `oracle_cloud_access` - Oracle Cloud

### API Access
- `openai_api` - OpenAI API

### CLI Tools
- `missing_cli_tool` - Dynamic detection

## Logging and Tracking

All capability gaps are logged to the database:

```python
from self_improvement.capability_detector import (
    get_gap_statistics,
    get_gaps_by_status
)

# Get statistics
stats = get_gap_statistics()
print(f"Total gaps: {stats['total']}")
print(f"Resolution rate: {stats['resolution_rate']:.1%}")

# Get pending gaps
pending = get_gaps_by_status("user_pending")
for gap in pending:
    print(f"- {gap['gap_description']}: {gap['status']}")
```

## CLI Commands

```bash
# Initialize the database table
python -m self_improvement.capability_detector init

# Detect a gap
python -m self_improvement.capability_detector detect \
    --task "Transcribe audio" \
    --error "No module named 'whisper'"

# List gaps by status
python -m self_improvement.capability_detector list --status detected

# Get statistics
python -m self_improvement.capability_detector stats

# Assess risk for a pattern
python -m self_improvement.risk_assessor --pattern audio_transcription

# Acquire a capability
python -m self_improvement.capability_acquirer acquire --pattern audio_transcription
```

## Integration with Weekly Reflection

The self-improvement system integrates with the weekly reflection:

1. Unresolved gaps are included in reflection context
2. Frequently encountered gaps suggest new skills
3. Successful acquisitions are logged as learnings

## Example: Complete Flow

```python
from self_improvement import (
    detect_capability_gap,
    assess_risk,
    acquire_capability,
    RiskLevel
)

def process_request(task, error=None, file_path=None):
    """Complete self-improvement flow."""

    # 1. Detect gap
    gap = detect_capability_gap(
        task_description=task,
        error_message=error or "",
        file_path=file_path or ""
    )

    if not gap:
        return {"status": "no_gap_detected"}

    # 2. Assess risk
    assessment = assess_risk(gap)

    # 3. Handle based on risk level
    if assessment.level in (RiskLevel.LOW, RiskLevel.MEDIUM):
        # Auto-acquire
        result = acquire_capability(gap)

        if result.success:
            return {
                "status": "acquired",
                "method": result.method,
                "skill": result.skill_created
            }
        else:
            return {
                "status": "failed",
                "error": result.error
            }

    else:
        # Need user approval
        return {
            "status": "approval_needed",
            "risk": assessment.level.value,
            "recommendation": assessment.recommendation,
            "required_inputs": assessment.requires_credentials
        }
```

## Important Notes

1. **Low-risk capabilities are acquired automatically** - no user intervention
2. **Medium-risk capabilities are acquired with notification**
3. **High/Critical risk requires explicit approval or credentials**
4. **All acquisitions are logged** for tracking and reflection
5. **Skills are created** for future reuse when possible

---
Created: 2026-02-01
System: Self-Improvement v1.0
