# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in PCP, please report it responsibly:

1. **Do NOT open a public issue** for security vulnerabilities
2. **Email**: Create a private security advisory via GitHub's Security tab
3. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 1 week
- **Resolution**: Depends on severity

## Security Best Practices

When deploying PCP:

### 1. Secrets Management
- **Never commit secrets** - Use environment variables
- **Use `.env` files** that are gitignored
- **Rotate credentials** regularly (Discord webhooks, API tokens)

### 2. Container Security
- Run containers with minimal privileges
- Don't mount host paths you don't need
- Keep Docker and base images updated

### 3. Authentication
- Store OAuth tokens securely (in gitignored directories)
- Use short-lived tokens where possible
- Audit access regularly

### 4. Data Protection
- The `vault/` directory contains sensitive data
- Ensure proper file permissions on host
- Use encrypted backups

## Known Security Considerations

1. **Discord Webhooks**: Webhook URLs are secrets - anyone with the URL can post messages
2. **Cloud Storage Tokens**: rclone OAuth tokens grant full storage access
3. **Browser Cookies**: Twitter/X cookies provide account access
4. **Host Mounts**: PCP can access mounted host directories

## Audit

This repository undergoes security audits before major releases. Findings are addressed promptly.
