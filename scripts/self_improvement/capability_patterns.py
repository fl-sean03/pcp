"""
Capability gap patterns for detection and resolution.

This module defines patterns that help identify what capability is missing
and how it might be resolved.
"""

from typing import Dict, List, Any

# Gap type categories
GAP_TYPE_FILE_PROCESSING = "file_processing"
GAP_TYPE_SERVICE_INTEGRATION = "service_integration"
GAP_TYPE_CLOUD_PROVIDER = "cloud_provider"
GAP_TYPE_CLI_TOOL = "cli_tool"
GAP_TYPE_API_ACCESS = "api_access"
GAP_TYPE_UNKNOWN = "unknown"

# Risk levels
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_CRITICAL = "critical"


CAPABILITY_PATTERNS: Dict[str, Dict[str, Any]] = {
    # ==========================================================================
    # FILE PROCESSING GAPS
    # ==========================================================================

    "audio_transcription": {
        "gap_type": GAP_TYPE_FILE_PROCESSING,
        "description": "Audio file transcription",
        "triggers": {
            "mime_types": ["audio/mpeg", "audio/wav", "audio/mp4", "audio/ogg", "audio/flac", "audio/x-m4a"],
            "extensions": [".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".wma"],
            "text_patterns": ["transcribe audio", "what does this say", "voice memo", "recording"],
        },
        "default_risk": RISK_LOW,
        "requires_user_input": False,
        "suggested_solutions": [
            {
                "name": "whisper",
                "type": "python_package",
                "install_command": "pip install openai-whisper",
                "description": "OpenAI Whisper - local, free, high quality",
                "test_command": "python -c \"import whisper; print('OK')\"",
            },
        ],
        "skill_template": "audio-transcription",
    },

    "video_processing": {
        "gap_type": GAP_TYPE_FILE_PROCESSING,
        "description": "Video file processing",
        "triggers": {
            "mime_types": ["video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"],
            "extensions": [".mp4", ".mov", ".avi", ".mkv", ".webm"],
            "text_patterns": ["video", "movie", "clip"],
        },
        "default_risk": RISK_LOW,
        "requires_user_input": False,
        "suggested_solutions": [
            {
                "name": "ffmpeg",
                "type": "system_package",
                "install_command": "sudo apt-get install -y ffmpeg",
                "description": "FFmpeg - video/audio processing toolkit",
                "test_command": "ffmpeg -version",
            },
        ],
        "skill_template": "video-processing",
    },

    # ==========================================================================
    # SERVICE INTEGRATIONS
    # ==========================================================================

    "notion_integration": {
        "gap_type": GAP_TYPE_SERVICE_INTEGRATION,
        "description": "Notion workspace access",
        "triggers": {
            "text_patterns": ["notion", "notion.so", "notion page", "notion database"],
            "error_patterns": ["notion", "NotionAPIError"],
        },
        "default_risk": RISK_MEDIUM,
        "requires_user_input": True,
        "required_inputs": ["NOTION_API_KEY"],
        "input_instructions": """
To get a Notion API key:
1. Go to https://www.notion.so/my-integrations
2. Click "New integration"
3. Give it a name (e.g., "PCP Integration")
4. Copy the "Internal Integration Token"
5. Share any pages/databases you want me to access with this integration
        """,
        "suggested_solutions": [
            {
                "name": "notion-client",
                "type": "python_package",
                "install_command": "pip install notion-client",
                "description": "Official Notion Python SDK",
                "test_command": "python -c \"from notion_client import Client; print('OK')\"",
            },
        ],
        "skill_template": "notion-integration",
    },

    "slack_integration": {
        "gap_type": GAP_TYPE_SERVICE_INTEGRATION,
        "description": "Slack workspace access",
        "triggers": {
            "text_patterns": ["slack", "slack message", "slack channel"],
            "error_patterns": ["slack", "SlackApiError"],
        },
        "default_risk": RISK_MEDIUM,
        "requires_user_input": True,
        "required_inputs": ["SLACK_BOT_TOKEN"],
        "input_instructions": """
To get a Slack Bot Token:
1. Go to https://api.slack.com/apps
2. Create a new app or select existing
3. Go to "OAuth & Permissions"
4. Copy the "Bot User OAuth Token" (starts with xoxb-)
        """,
        "suggested_solutions": [
            {
                "name": "slack-sdk",
                "type": "python_package",
                "install_command": "pip install slack-sdk",
                "description": "Official Slack Python SDK",
                "test_command": "python -c \"from slack_sdk import WebClient; print('OK')\"",
            },
        ],
        "skill_template": "slack-integration",
    },

    "jira_integration": {
        "gap_type": GAP_TYPE_SERVICE_INTEGRATION,
        "description": "Jira project access",
        "triggers": {
            "text_patterns": ["jira", "jira ticket", "jira issue", "atlassian"],
            "error_patterns": ["jira", "JIRAError"],
        },
        "default_risk": RISK_MEDIUM,
        "requires_user_input": True,
        "required_inputs": ["JIRA_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"],
        "input_instructions": """
To get Jira API credentials:
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. I'll also need your Jira URL (e.g., yourcompany.atlassian.net)
4. And your Jira email address
        """,
        "suggested_solutions": [
            {
                "name": "jira",
                "type": "python_package",
                "install_command": "pip install jira",
                "description": "Python Jira library",
                "test_command": "python -c \"from jira import JIRA; print('OK')\"",
            },
        ],
        "skill_template": "jira-integration",
    },

    # ==========================================================================
    # CLOUD PROVIDERS
    # ==========================================================================

    "aws_access": {
        "gap_type": GAP_TYPE_CLOUD_PROVIDER,
        "description": "AWS cloud access",
        "triggers": {
            "text_patterns": ["aws", "amazon web services", "ec2", "s3", "lambda", "dynamodb"],
            "error_patterns": ["NoCredentialsError", "botocore", "aws configure"],
        },
        "default_risk": RISK_HIGH,
        "requires_user_input": True,
        "required_inputs": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION"],
        "input_instructions": """
To get AWS credentials:
1. Go to AWS Console → IAM → Users → Your User → Security credentials
2. Create a new Access Key
3. I'll need:
   - Access Key ID
   - Secret Access Key
   - Default region (e.g., us-east-1)

Note: This will allow me to manage AWS resources on your behalf.
        """,
        "suggested_solutions": [
            {
                "name": "boto3",
                "type": "python_package",
                "install_command": "pip install boto3",
                "description": "AWS SDK for Python",
                "test_command": "python -c \"import boto3; print('OK')\"",
            },
            {
                "name": "awscli",
                "type": "python_package",
                "install_command": "pip install awscli",
                "description": "AWS CLI",
                "test_command": "aws --version",
            },
        ],
        "skill_template": "aws-cloud",
    },

    "oracle_cloud_access": {
        "gap_type": GAP_TYPE_CLOUD_PROVIDER,
        "description": "Oracle Cloud Infrastructure access",
        "triggers": {
            "text_patterns": ["oracle cloud", "oci", "oracle vm", "oracle instance"],
            "error_patterns": ["oci", "ConfigFileNotFound"],
        },
        "default_risk": RISK_HIGH,
        "requires_user_input": True,
        "required_inputs": ["OCI_CONFIG"],
        "input_instructions": """
To set up Oracle Cloud access:
1. Go to Oracle Cloud Console → Identity → Users → Your User
2. Under "API Keys", click "Add API Key"
3. Download the config file
4. I'll need the contents of your ~/.oci/config file

Note: This will allow me to manage OCI resources on your behalf.
        """,
        "suggested_solutions": [
            {
                "name": "oci",
                "type": "python_package",
                "install_command": "pip install oci",
                "description": "Oracle Cloud Infrastructure SDK",
                "test_command": "python -c \"import oci; print('OK')\"",
            },
        ],
        "skill_template": "oracle-cloud",
    },

    "gcp_access": {
        "gap_type": GAP_TYPE_CLOUD_PROVIDER,
        "description": "Google Cloud Platform access",
        "triggers": {
            "text_patterns": ["gcp", "google cloud", "gce", "gcs", "bigquery"],
            "error_patterns": ["google.auth", "DefaultCredentialsError"],
        },
        "default_risk": RISK_HIGH,
        "requires_user_input": True,
        "required_inputs": ["GOOGLE_APPLICATION_CREDENTIALS"],
        "input_instructions": """
To set up GCP access:
1. Go to GCP Console → IAM & Admin → Service Accounts
2. Create a service account or select existing
3. Create a key (JSON format)
4. Share the JSON file contents with me

Note: This will allow me to manage GCP resources on your behalf.
        """,
        "suggested_solutions": [
            {
                "name": "google-cloud",
                "type": "python_package",
                "install_command": "pip install google-cloud-core",
                "description": "Google Cloud SDK",
                "test_command": "python -c \"from google.cloud import storage; print('OK')\"",
            },
        ],
        "skill_template": "gcp-cloud",
    },

    # ==========================================================================
    # CLI TOOLS
    # ==========================================================================

    "missing_cli_tool": {
        "gap_type": GAP_TYPE_CLI_TOOL,
        "description": "Missing command-line tool",
        "triggers": {
            "error_patterns": [
                "command not found",
                "not recognized as an internal or external command",
                "No such file or directory",
                "executable file not found",
            ],
        },
        "default_risk": RISK_LOW,
        "requires_user_input": False,
        "dynamic_resolution": True,  # Tool name extracted from error
        "suggested_solutions": [],  # Populated dynamically
        "skill_template": None,  # No skill needed for basic tools
    },

    # ==========================================================================
    # API ACCESS
    # ==========================================================================

    "openai_api": {
        "gap_type": GAP_TYPE_API_ACCESS,
        "description": "OpenAI API access",
        "triggers": {
            "text_patterns": ["openai", "gpt-4", "chatgpt", "dall-e"],
            "error_patterns": ["openai", "AuthenticationError", "OPENAI_API_KEY"],
        },
        "default_risk": RISK_MEDIUM,
        "requires_user_input": True,
        "required_inputs": ["OPENAI_API_KEY"],
        "input_instructions": """
To get an OpenAI API key:
1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Note: API usage will be charged to your OpenAI account
        """,
        "suggested_solutions": [
            {
                "name": "openai",
                "type": "python_package",
                "install_command": "pip install openai",
                "description": "OpenAI Python SDK",
                "test_command": "python -c \"import openai; print('OK')\"",
            },
        ],
        "skill_template": "openai-api",
    },
}


# Common CLI tools and their installation commands
CLI_TOOL_INSTALLATIONS: Dict[str, Dict[str, str]] = {
    "ffmpeg": {
        "apt": "sudo apt-get install -y ffmpeg",
        "brew": "brew install ffmpeg",
        "description": "Audio/video processing",
    },
    "jq": {
        "apt": "sudo apt-get install -y jq",
        "brew": "brew install jq",
        "description": "JSON processor",
    },
    "curl": {
        "apt": "sudo apt-get install -y curl",
        "brew": "brew install curl",
        "description": "HTTP client",
    },
    "wget": {
        "apt": "sudo apt-get install -y wget",
        "brew": "brew install wget",
        "description": "HTTP downloader",
    },
    "imagemagick": {
        "apt": "sudo apt-get install -y imagemagick",
        "brew": "brew install imagemagick",
        "description": "Image manipulation",
    },
    "pandoc": {
        "apt": "sudo apt-get install -y pandoc",
        "brew": "brew install pandoc",
        "description": "Document converter",
    },
    "tesseract": {
        "apt": "sudo apt-get install -y tesseract-ocr",
        "brew": "brew install tesseract",
        "description": "OCR engine",
    },
    "poppler": {
        "apt": "sudo apt-get install -y poppler-utils",
        "brew": "brew install poppler",
        "description": "PDF utilities",
    },
}


def get_pattern_for_gap(gap_identifier: str) -> Dict[str, Any]:
    """Get the pattern definition for a gap identifier."""
    return CAPABILITY_PATTERNS.get(gap_identifier, {})


def find_matching_patterns(
    text: str = "",
    mime_type: str = "",
    extension: str = "",
    error_message: str = ""
) -> List[str]:
    """
    Find all patterns that match the given criteria.

    Returns list of pattern identifiers (keys from CAPABILITY_PATTERNS).
    """
    matches = []

    for pattern_id, pattern in CAPABILITY_PATTERNS.items():
        triggers = pattern.get("triggers", {})

        # Check MIME type
        if mime_type and mime_type in triggers.get("mime_types", []):
            matches.append(pattern_id)
            continue

        # Check extension
        if extension:
            ext_lower = extension.lower()
            if ext_lower in triggers.get("extensions", []):
                matches.append(pattern_id)
                continue

        # Check text patterns
        text_lower = text.lower()
        for text_pattern in triggers.get("text_patterns", []):
            if text_pattern.lower() in text_lower:
                matches.append(pattern_id)
                break
        else:
            # Check error patterns
            error_lower = error_message.lower()
            for error_pattern in triggers.get("error_patterns", []):
                if error_pattern.lower() in error_lower:
                    matches.append(pattern_id)
                    break

    return list(set(matches))  # Remove duplicates


def get_cli_tool_install_command(tool_name: str, platform: str = "linux") -> str:
    """Get the installation command for a CLI tool."""
    tool = CLI_TOOL_INSTALLATIONS.get(tool_name.lower(), {})

    if platform == "linux":
        return tool.get("apt", f"# Unknown tool: {tool_name}")
    elif platform == "darwin":
        return tool.get("brew", f"# Unknown tool: {tool_name}")
    else:
        return f"# Unknown platform: {platform}"
