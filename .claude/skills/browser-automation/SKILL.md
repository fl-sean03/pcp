---
name: browser-automation
description: Interactive web tasks, browser login, click, scroll, form interaction, authenticated sessions, Playwright MCP (project)
---

# Browser Automation Skill

Use the Playwright MCP server for interactive web tasks that require login, clicking, scrolling, or form interaction.

## Quick Start

**When to use Browser Automation:**
- Pages requiring authentication (login, sessions)
- Interactive UI (clicking buttons, filling forms)
- Dynamic content (scrolling to load more)
- Screenshots of authenticated pages
- Multi-step web workflows

**When NOT to use Browser (use these instead):**
- WebSearch: Public information searches
- WebFetch: Reading public pages (no login)
- curl: Simple API calls

## Tool Selection Guide

| Need | Tool | Why |
|------|------|-----|
| Search the web | WebSearch | Fast, no browser needed |
| Read a public URL | WebFetch | Simpler, converts HTML to markdown |
| Login to a site | Playwright Browser | Handles auth, cookies, sessions |
| Click a button | Playwright Browser | Interactive elements |
| Fill a form | Playwright Browser | Form fields, validation |
| Scroll to load | Playwright Browser | Dynamic/infinite scroll |
| Screenshot dashboard | Playwright Browser | Authenticated page |
| API endpoint | curl | Direct HTTP, no browser |

## Examples: When to Use Each

### Use WebSearch/WebFetch

```
"What's the latest React documentation?"
→ Use WebSearch

"Summarize this blog post: https://example.com/post"
→ Use WebFetch

"Find documentation on Python asyncio"
→ Use WebSearch
```

### Use Playwright Browser

```
"Check my Twitter mentions"
→ Use browser_navigate to twitter.com, then browser_snapshot

"Scroll through my LinkedIn feed"
→ Use browser_navigate, then browser_evaluate with scroll

"Fill out this form and submit"
→ Use browser_fill_form or browser_type + browser_click

"Take a screenshot of my dashboard"
→ Use browser_navigate + browser_take_screenshot

"Click the export button on this SaaS tool"
→ Use browser_snapshot to find ref, then browser_click
```

## Playwright MCP Tools

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `browser_navigate` | Go to URL | Start any session |
| `browser_snapshot` | Get accessibility tree | Before clicking (find element refs) |
| `browser_click` | Click element | Buttons, links, interactive elements |
| `browser_type` | Type into field | Text inputs, search boxes |
| `browser_fill_form` | Fill multiple fields | Login forms, multi-field forms |
| `browser_take_screenshot` | Capture image | Visual documentation |
| `browser_evaluate` | Run JavaScript | Scroll, complex interactions |
| `browser_press_key` | Press keyboard key | Enter, Escape, arrows |
| `browser_hover` | Hover over element | Reveal tooltips, dropdowns |
| `browser_select_option` | Select dropdown | Dropdown menus |
| `browser_wait_for` | Wait for text/time | Content loading |
| `browser_tabs` | Manage tabs | Multiple pages |
| `browser_close` | Close browser | End session |

## Common Workflows

### Login to a Site

```
1. browser_navigate → url: "https://site.com/login"
2. browser_snapshot → find form field refs
3. browser_fill_form → username, password fields
4. browser_click → submit button (ref from snapshot)
5. browser_wait_for → text: "Dashboard" (or success indicator)
```

### Extract Content After Login

```
1. Login workflow (above)
2. browser_navigate → target page
3. browser_snapshot → get page content as accessibility tree
4. Process the content
```

### Scroll and Load More

```
1. browser_navigate → page with infinite scroll
2. browser_evaluate → function: "async (page) => { window.scrollTo(0, document.body.scrollHeight); }"
3. browser_wait_for → time: 2 (seconds for content to load)
4. browser_snapshot → get loaded content
5. Repeat 2-4 as needed
```

### Fill and Submit Form

```
1. browser_navigate → form page
2. browser_snapshot → find field refs
3. browser_fill_form → fields: [
     {name: "Email", type: "textbox", ref: "R123", value: "email@example.com"},
     {name: "Phone", type: "textbox", ref: "R124", value: "555-1234"}
   ]
4. browser_click → submit button ref
5. browser_wait_for → confirmation text
```

## Persistent Sessions

The Playwright MCP can maintain logged-in sessions across Claude Code restarts:

```bash
# Setup with persistent browser profile
claude mcp add playwright -- npx @playwright/mcp@latest --user-data-dir ~/.playwright-data/pcp-browser
```

**Benefits:**
- Login once, stay logged in
- Cookies and local storage preserved
- Faster subsequent interactions
- No re-authentication needed

## Browser Snapshot vs Screenshot

| Method | Output | Use For |
|--------|--------|---------|
| `browser_snapshot` | Accessibility tree (text) | Finding elements, extracting text, action refs |
| `browser_take_screenshot` | Image file | Visual documentation, debugging |

**Rule:** Use `browser_snapshot` for actions, `browser_take_screenshot` for visuals.

## When User Says...

| User Request | What To Do |
|--------------|------------|
| "Check my Twitter mentions" | Navigate to twitter.com/notifications, snapshot |
| "Log in to X and check Y" | Login workflow, then navigate + snapshot |
| "Scroll through my feed" | Navigate, evaluate scroll, wait, snapshot |
| "Fill out this form" | Navigate, snapshot for refs, fill_form, click submit |
| "Screenshot my dashboard" | Navigate, wait for load, take_screenshot |
| "Click the button that says X" | Snapshot to find ref, click with ref |
| "What's on this page?" | If public: WebFetch. If login: browser + snapshot |

## Error Handling

**Browser not installed:**
```
Error: Browser not found
→ Use browser_install tool
```

**Element not found:**
```
Error: Element ref not found
→ Run browser_snapshot first to get current refs
```

**Login expired:**
```
Content shows login page instead of expected content
→ Re-authenticate or use persistent user-data-dir
```

## Integration with PCP

Browser automation works with PCP capabilities:

1. **Extract → Capture**: Get content via browser, capture to vault
   ```python
   content = browser_snapshot()
   smart_capture(f"From Twitter feed: {content}")
   ```

2. **Browser → Email**: Draft email based on browser data
   ```python
   data = browser_get_form_data()
   create_draft(to="x@y.com", subject="Form data", body=data)
   ```

3. **Browser → Knowledge**: Store permanent facts found in browser
   ```python
   price = extract_from_browser()
   add_knowledge(f"Widget price is {price}", category="fact")
   ```

## Related Skills

- **native-tools** - When CLI tools suffice (curl for APIs)
- **email-processing** - For Outlook email (use Graph API, not browser)
- **vault-operations** - Capture browser-extracted content
- **knowledge-base** - Store permanent facts from browser research
