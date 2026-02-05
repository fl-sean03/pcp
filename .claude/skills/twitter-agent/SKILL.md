---
name: twitter-agent
description: Twitter, tweet, timeline, mentions, X, social media, feed, engagement, replies, drafts, scoring (project)
---

# Twitter Agent

Twitter/X social management agent. Extracts feed, scores posts for relevance, and creates draft responses for the user's approval.

## Critical Rules

1. **DRAFTS ONLY** - Never auto-post anything. All content must be approved by the user.
2. **TOP 0.01% ONLY** - Only surface posts scoring > 0.9 (extremely selective)
3. **Follow Operating Manual** - See `references/operating-manual.md` for voice, audience, and approval gates

## Quick Start

```bash
# Extract posts from timeline (requires Playwright MCP login)
python twitter.py extract --limit 20

# Score unscored posts (surfaces high-relevance only)
python twitter.py score-feed

# View high-relevance posts
python twitter.py high-relevance

# List pending drafts
python twitter.py drafts

# Create a draft reply (does NOT post)
python twitter.py draft-reply POST_ID "Response text"
```

## Workflow

```
Timeline ─> Extract ─> Score ─> Present High-Relevance ─> User Reviews
                                        │
                            Create Drafts (if warranted)
                                        │
                              User Approves/Rejects
                                        │
                              User Posts Manually
```

## Setup: Playwright MCP

Twitter extraction requires Playwright MCP with persistent login:

```bash
# Install Playwright MCP with persistent browser session
claude mcp add playwright -- npx @playwright/mcp@latest --user-data-dir ~/.playwright-data/twitter

# First time: log in via the browser
# Subsequent runs: session persists
```

## Target Audience (Score HIGH)

Per the user's Operating Manual, prioritize these audiences:
- AI for science researchers with serious engineering taste
- HPC, scientific computing, data infra engineers
- Lab automation and autonomous experimentation operators
- Hard tech founders and early employees (materials, energy, defense)
- Defense and energy program people who care about capability
- Deep tech investors with real full stack instincts
- Materials science graduate students and postdocs
- Industry R&D engineers (batteries, catalysts, semiconductors, aerospace)

## Score LOW (Avoid)

- Generic AI hype accounts
- Engagement farmers
- People who only want vibes and hot takes
- Content about generic AI trends, not scientific computing

## Engagement Rules

The user should ONLY engage when he can:
- Add a missing system detail or infrastructure layer
- Ask a pointed, specific question
- Clarify a technical distinction
- Provide HPC/simulation workflow insight
- Build a useful relationship with someone in target audience

## Functions

### Feed Extraction

```python
from twitter import extract_feed, store_extracted_post

# Get extraction instructions (uses Playwright MCP)
result = extract_feed(limit=20)
# Follow the instructions with browser tools

# Store each extracted tweet
store_extracted_post(
    post_id="1234567890",
    author_name="Display Name",
    author_handle="username",
    content="Tweet content here",
    engagement={"likes": 50, "retweets": 10}
)
```

### Relevance Scoring

```python
from twitter import score_relevance, score_feed, get_high_relevance_posts

# Score a single post
result = score_relevance(post)
# Returns: {score, audience_match, engagement_fit, reasoning, suggested_action}

# Score all unscored posts and get high-relevance ones (>0.9)
high_relevance = score_feed(min_score=0.9)

# Get already-scored high-relevance posts
posts = get_high_relevance_posts(min_score=0.9)
```

### Draft Creation (NEVER Auto-Posts)

```python
from twitter import draft_reply, draft_quote, draft_dm, get_pending_drafts

# Create draft reply to a post
result = draft_reply(post_id=42, suggested_text="Great point about HPC...")
# Returns: {success, draft_id, message: "the user must review and post manually"}

# Create draft quote tweet
result = draft_quote(post_id=42, suggested_text="This connects to...")

# Create draft DM
result = draft_dm(handle="username", suggested_text="Quick question...")

# List all pending drafts for the user to review
drafts = get_pending_drafts()
```

### Draft Management

```python
from twitter import approve_draft, reject_draft

# the user approves a draft (still must manually post)
approve_draft(draft_id=1)

# the user rejects a draft
reject_draft(draft_id=1)
```

## CLI Commands

```bash
# Extract tweets from timeline
python twitter.py extract [--limit N]

# Store a tweet manually
python twitter.py store POST_ID --author "Name" --handle "username" --content "Text"

# Score all unscored posts
python twitter.py score-feed [--min-score 0.9] [--show-all]

# Score a single post
python twitter.py score-post DB_ID

# Show high-relevance posts
python twitter.py high-relevance [--min-score 0.9]

# List pending drafts
python twitter.py drafts

# Create drafts (DOES NOT POST)
python twitter.py draft-reply POST_ID "Response text"
python twitter.py draft-quote POST_ID "Quote text"
python twitter.py draft-dm HANDLE "DM text"

# Approve/reject drafts
python twitter.py approve DRAFT_ID
python twitter.py reject DRAFT_ID
```

## When User Says...

| User Says | Action |
|-----------|--------|
| "Check my Twitter" | Extract feed, score, show high-relevance posts |
| "Any good engagement opportunities?" | `python twitter.py high-relevance` |
| "Draft a reply to that post" | `draft_reply(post_id, text)` + show draft |
| "Reply to @username about X" | Search posts, create `draft_reply` |
| "DM that person" | `draft_dm(handle, text)` |
| "Show pending drafts" | `python twitter.py drafts` |
| "Approve draft 5" | `approve_draft(5)` + remind the user to post manually |

## Approval Gates (From Operating Manual)

**Can post without asking:**
- Technical observations with no sensitive claims
- Neutral questions
- Replies that are not political and not personal

**Must get user approval on:**
- Any thread
- Anything that names a person as a claim or critique
- Anything that references a partner, lab, employer, or program
- Anything with a strong defense or policy stance
- Anything mentioning the user's product names, fundraising, hiring, or partnerships

## Voice Guidelines (From Operating Manual)

- Direct, technical, calm
- Curious and skeptical
- High signal, low drama
- Precise about what is known vs assumed
- Short sentences
- No emoji unless it adds clarity (max one)
- No hashtags
- No em dashes

**Ban list:**
- programmable matter (unless milestone)
- revolutionize, disrupt, democratize, game changer, huge

## Database Tables

### social_feed
Stores all extracted posts:
| Column | Description |
|--------|-------------|
| id | Database ID |
| platform | Always "twitter" |
| post_id | Twitter's post ID |
| author_name | Display name |
| author_handle | @handle (no @) |
| content | Tweet text |
| engagement | JSON: {likes, retweets, replies} |
| relevance_score | 0.0-1.0 from scoring |
| suggested_action | reply/quote/like/ignore |
| action_taken | What was done |
| captured_at | When extracted |

### twitter_drafts
Stores draft responses:
| Column | Description |
|--------|-------------|
| id | Draft ID |
| post_id | FK to social_feed (for replies/quotes) |
| draft_type | reply/quote/dm |
| target_handle | For DMs |
| draft_text | Draft content |
| status | pending/approved/rejected |
| created_at | When drafted |
| approved_at | When approved |

## Related Skills

- **browser-automation**: How to use Playwright MCP
- **vault-operations**: Captures for context
- **relationship-intelligence**: Track people engaged with
- **pcp-operations**: System overview

## References

- `references/operating-manual.md` - the user's full X Operating Manual

---

**Remember**: This is a DRAFT-ONLY system. Never auto-post. the user must manually post all content.
