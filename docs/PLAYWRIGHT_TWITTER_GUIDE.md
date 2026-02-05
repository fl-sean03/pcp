# Playwright-Twitter Integration Guide for PCP

**Version:** 1.0.0
**Last Updated:** 2026-01-13
**Purpose:** Comprehensive guide for implementing Twitter integration via Playwright MCP

---

## Overview

PCP accesses Twitter/X via the **Playwright MCP** (Model Context Protocol) server. This provides browser automation capabilities through an accessibility tree representation rather than vision/screenshots.

### Key Characteristics
- **No API needed** - Uses browser automation instead of Twitter's API
- **Cookie-based auth** - No password storage required
- **Persistent sessions** - Browser profile maintains login state
- **Accessibility tree** - Pages represented as structured elements with refs (e.g., `e1234`)
- **Context intensive** - Each snapshot consumes significant tokens

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Claude Code Session                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────────┐         ┌──────────────────────────────────┐ │
│   │  PCP Agent   │ ──────► │     Playwright MCP Server        │ │
│   │  (Main)      │         │     (npx @playwright/mcp)        │ │
│   └──────────────┘         └──────────────────────────────────┘ │
│                                       │                          │
│                                       ▼                          │
│                            ┌──────────────────────┐             │
│                            │   Chromium Browser   │             │
│                            │   (Headless Mode)    │             │
│                            └──────────────────────┘             │
│                                       │                          │
│                                       ▼                          │
│                            ┌──────────────────────┐             │
│                            │   Twitter/X.com      │             │
│                            │   (Authenticated)    │             │
│                            └──────────────────────┘             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Locations

| File | Path | Purpose |
|------|------|---------|
| **Twitter Cookies** | `config/twitter_cookies.json` | Authentication cookies (gitignored) |
| **Browser Profile** | `~/.cache/pcp-browser-profile/` | Persistent browser state (login, settings) |
| **MCP Config** | `~/.claude.json` | Playwright MCP server configuration |
| **X Operating Manual** | `personal/x_operating_manual.md` | User's voice, style, content pillars (gitignored) |

---

## Configuration

### 1. MCP Server Setup (`~/.claude.json`)

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": [
        "@playwright/mcp@latest",
        "--user-data-dir",
        "~/.cache/pcp-browser-profile"
      ],
      "env": {}
    }
  }
}
```

**Important:** MCP servers only load at Claude Code session start. If Playwright tools aren't available, restart Claude Code.

### 2. Cookie Format

Cookies are stored in Netscape/browser extension format:

```json
[
  {
    "domain": ".x.com",
    "name": "auth_token",
    "value": "...",
    "path": "/",
    "secure": true,
    "httpOnly": true,
    "expirationDate": 1780342244
  },
  {
    "domain": ".x.com",
    "name": "ct0",
    "value": "...",
    "path": "/",
    "sameSite": "lax"
  }
]
```

**Critical cookies for authentication:**
- `auth_token` - Primary authentication token
- `ct0` - CSRF token (required for actions)
- `twid` - User ID token

---

## Available MCP Tools

### Navigation & Snapshots
| Tool | Purpose |
|------|---------|
| `mcp__playwright__browser_navigate` | Go to a URL |
| `mcp__playwright__browser_snapshot` | Get accessibility tree of current page |
| `mcp__playwright__browser_navigate_back` | Go back |
| `mcp__playwright__browser_wait_for` | Wait for text/time |

### Interaction
| Tool | Purpose |
|------|---------|
| `mcp__playwright__browser_click` | Click an element by ref |
| `mcp__playwright__browser_type` | Type into an input field |
| `mcp__playwright__browser_hover` | Hover over an element |
| `mcp__playwright__browser_press_key` | Press a keyboard key |

### Forms & Files
| Tool | Purpose |
|------|---------|
| `mcp__playwright__browser_fill_form` | Fill multiple form fields |
| `mcp__playwright__browser_file_upload` | Upload files |
| `mcp__playwright__browser_select_option` | Select dropdown option |

### Session Management
| Tool | Purpose |
|------|---------|
| `mcp__playwright__browser_close` | Close browser |
| `mcp__playwright__browser_tabs` | Manage tabs |

---

## Twitter Navigation Patterns

### Key URLs

| Page | URL | Notes |
|------|-----|-------|
| Home/Timeline | `https://x.com/home` | Main feed |
| Notifications | `https://x.com/notifications` | All notifications |
| Messages/DMs | `https://x.com/messages` | **Encrypted - requires passcode** |
| Profile | `https://x.com/{username}` | User's profile |
| Compose | Click compose button | Or keyboard shortcut |
| Search | `https://x.com/search?q=query` | Search results |

### Example: Navigate to Home

```python
# Using MCP tool
mcp__playwright__browser_navigate(url="https://x.com/home")
mcp__playwright__browser_wait_for(time=2)  # Wait for load
mcp__playwright__browser_snapshot()  # Get page state
```

### Example: Check Notifications

```python
mcp__playwright__browser_navigate(url="https://x.com/notifications")
mcp__playwright__browser_wait_for(text="Notifications")
mcp__playwright__browser_snapshot()
# Parse snapshot for notification items
```

---

## Authentication Flow

### Cookie Injection (Recommended)

1. Load cookies from config file
2. Navigate to Twitter
3. Cookies auto-apply from persistent profile

```python
# First time setup - inject cookies
import json

with open('config/twitter_cookies.json') as f:
    cookies = json.load(f)

# Use Playwright for cookie injection
# Navigate to x.com first, then inject cookies via browser context
```

### Session Persistence

After initial cookie injection, the browser profile maintains the session. Subsequent sessions should auto-authenticate.

---

## Known Limitations

### 1. Encrypted DMs
- Twitter DMs show as encrypted
- Require user to enter passcode to view
- **Agent cannot read DMs** without passcode

### 2. Context Window Usage
- Each `browser_snapshot` returns full accessibility tree
- Large pages (timeline) consume 2,000-5,000+ tokens per snapshot
- Rapid navigation exhausts context quickly

### 3. Rate Limiting
- Twitter may rate limit automated browsing
- Cloudflare may block based on patterns
- Use natural timing between actions

### 4. No Vision
- Playwright MCP uses accessibility tree, not screenshots
- Cannot "see" images in tweets
- Cannot solve visual CAPTCHAs

### 5. Dynamic Content
- Timeline loads dynamically
- May need multiple snapshots to see all content
- Scrolling required for more posts

---

## User Profile Configuration

**For voice alignment when composing tweets**, create a personal profile file:

`personal/x_operating_manual.md`:
```markdown
# X/Twitter Operating Manual

## Profile
- **Handle**: @yourhandle
- **Name**: Your Name
- **Bio**: Your bio

## Voice Characteristics
- Concise - Short, punchy statements
- Technical - Uses industry terminology naturally
- Authentic - No corporate speak

## Content Pillars
1. Your topic 1
2. Your topic 2
3. Your topic 3
```

This file is gitignored to keep personal information private.

---

## Architecture Considerations

### Context Optimization Problem

Playwright MCP is context-intensive. Each snapshot can consume thousands of tokens. For a long-running agent session, this creates problems:

**Current Flow (Context Heavy):**
```
User Request → Main Agent → Playwright Snapshot → Parse → Response
                              ↑
                        (2-5K tokens each)
```

### Proposed Dual-Agent Architecture

**Optimized Flow:**
```
┌─────────────────┐     ┌─────────────────────────────────────┐
│                 │     │       Browser Agent (Subagent)      │
│   Main Agent    │────►│  - Handles all Playwright calls     │
│   (PCP Core)    │     │  - Returns structured summaries     │
│                 │◄────│  - Isolated context window          │
└─────────────────┘     └─────────────────────────────────────┘
        │                              │
        │                              ▼
        │                    ┌──────────────────┐
        │                    │  Playwright MCP  │
        │                    │  (Full snapshots)│
        │                    └──────────────────┘
        ▼
┌─────────────────┐
│      User       │
└─────────────────┘
```

**Benefits:**
1. Main agent context preserved for conversation
2. Browser agent context isolated and disposable
3. Structured data returned instead of raw snapshots
4. Better token efficiency

**Implementation with Task Tool:**
```python
# Main agent delegates to browser subagent
result = Task(
    subagent_type="Explore",  # or custom browser agent
    prompt="Check Twitter notifications and return structured summary",
    model="haiku"  # Use cheaper model for browser tasks
)
```

---

## Integration with PCP

### Smart Capture Integration

When Twitter content is retrieved, it should flow through PCP's capture system:

```python
from vault_v2 import smart_capture

# After getting notification data from Playwright
notification_text = "@someone replied to your tweet about topic"
smart_capture(notification_text, source="twitter_notification")
```

### Task Creation

Twitter interactions can create tasks:
```python
from vault_v2 import get_tasks

# DM mentions deadline → auto-create task
# Notification about important reply → suggest follow-up task
```

### Knowledge Integration

Store insights about Twitter audience/engagement:
```python
from knowledge import add_knowledge

add_knowledge(
    "High engagement on topic X content",
    category="preference",
    project="Twitter"
)
```

---

## Error Handling

### Common Issues

| Error | Cause | Solution |
|-------|-------|----------|
| `MCP server not available` | Session started before config | Restart Claude Code |
| `Cloudflare challenge` | IP blocked | Use different network or wait |
| `Element not found` | Dynamic loading | Add wait time before snapshot |
| `Session expired` | Cookies expired | Re-inject fresh cookies |

### Recovery Pattern

```python
# If navigation fails, try recovery
try:
    mcp__playwright__browser_navigate(url="https://x.com/home")
except:
    # Close and restart browser
    mcp__playwright__browser_close()
    # Re-launch with cookies
    # ... cookie injection flow
```

---

## Security Notes

1. **Cookie files contain sensitive auth tokens** - Do not commit to git
2. **Browser profile contains session data** - Keep in gitignore
3. **ct0 token is CSRF protection** - Required for POST actions
4. **Cookies expire** - Check expiration dates, refresh as needed

### Cookie Expiration Check

```python
import json
import time

with open('config/twitter_cookies.json') as f:
    cookies = json.load(f)

for cookie in cookies:
    if 'expirationDate' in cookie:
        exp = cookie['expirationDate']
        if exp < time.time():
            print(f"EXPIRED: {cookie['name']}")
        else:
            days_left = (exp - time.time()) / 86400
            print(f"{cookie['name']}: {days_left:.0f} days remaining")
```

---

## Next Steps for Implementation

1. **Create Twitter Skill**
   - Wrap Playwright operations in skill functions
   - Implement structured data extraction
   - Add voice alignment for compose operations

2. **Implement Dual-Agent Architecture**
   - Create browser subagent type
   - Define structured response format
   - Test context isolation

3. **Add Scheduled Checks**
   - Periodic notification checks
   - Engagement monitoring
   - Auto-capture important interactions

4. **Voice Alignment**
   - Load operating manual on compose
   - Validate drafts against style guidelines
   - Suggest improvements based on past performance

---

## Appendix: Full Cookie List

| Cookie | Purpose | HttpOnly | Expiration |
|--------|---------|----------|------------|
| `auth_token` | Primary auth | Yes | ~6 months |
| `ct0` | CSRF token | No | ~6 months |
| `twid` | User ID | No | ~1 year |
| `guest_id` | Guest tracking | No | ~6 months |
| `kdt` | Device token | Yes | ~6 months |
| `personalization_id` | Personalization | No | ~1 year |
| `__cf_bm` | Cloudflare bot mgmt | Yes | 30 min |

---

*Document generated for PCP Twitter integration*
