#!/usr/bin/env python3
"""
PCP Twitter Agent - Twitter feed extraction and draft management.

Uses Playwright MCP (when available) to extract tweets from timeline.
Stores posts via social_feed.py for processing.
Creates DRAFT responses only - never auto-posts.
"""

import sqlite3
import json
import os
import subprocess
import re
from datetime import datetime
from typing import Optional, List, Dict, Any

# Support both container and local development paths
VAULT_PATH = "/workspace/vault/vault.db"
if not os.path.exists(os.path.dirname(VAULT_PATH)) and os.path.exists(os.path.join(os.environ.get("PCP_DIR", "/workspace"), "vault")):
    VAULT_PATH = os.path.join(os.environ.get("PCP_DIR", "/workspace"), "vault/vault.db")

# Import social_feed functions
try:
    from social_feed import store_post, post_exists, get_post, update_action
except ImportError:
    # Handle running from different directory
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from social_feed import store_post, post_exists, get_post, update_action


# ============================================================================
# Draft Storage Functions
# ============================================================================

def _ensure_drafts_table():
    """Ensure twitter_drafts table exists."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS twitter_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            draft_type TEXT NOT NULL,
            target_handle TEXT,
            draft_text TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            approved_at TEXT,
            FOREIGN KEY (post_id) REFERENCES social_feed(id)
        )
    """)

    conn.commit()
    conn.close()


def store_draft(
    draft_type: str,
    draft_text: str,
    post_id: Optional[int] = None,
    target_handle: Optional[str] = None
) -> int:
    """
    Store a draft response in the database.

    IMPORTANT: This only stores drafts. Never auto-posts.

    Args:
        draft_type: Type of draft (reply, quote, dm)
        draft_text: The draft text content
        post_id: Database ID of the post being responded to (for replies/quotes)
        target_handle: @handle for DMs

    Returns:
        The ID of the created draft
    """
    _ensure_drafts_table()

    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO twitter_drafts (post_id, draft_type, target_handle, draft_text, status, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
    """, (post_id, draft_type, target_handle, draft_text, datetime.now().isoformat()))

    draft_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return draft_id


def get_pending_drafts() -> List[Dict[str, Any]]:
    """Get all pending drafts."""
    _ensure_drafts_table()

    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT d.id, d.post_id, d.draft_type, d.target_handle, d.draft_text,
               d.status, d.created_at, d.approved_at,
               s.author_handle, s.content as original_content
        FROM twitter_drafts d
        LEFT JOIN social_feed s ON d.post_id = s.id
        WHERE d.status = 'pending'
        ORDER BY d.created_at DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def approve_draft(draft_id: int) -> bool:
    """
    Mark a draft as approved.

    NOTE: This marks the draft as ready. the user must still manually post it.
    """
    _ensure_drafts_table()

    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE twitter_drafts
        SET status = 'approved', approved_at = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), draft_id))

    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return updated


def reject_draft(draft_id: int) -> bool:
    """Mark a draft as rejected."""
    _ensure_drafts_table()

    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE twitter_drafts
        SET status = 'rejected'
        WHERE id = ?
    """, (draft_id,))

    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return updated


# ============================================================================
# Feed Extraction Functions
# ============================================================================

def extract_feed(limit: int = 20) -> Dict[str, Any]:
    """
    Extract posts from Twitter timeline using Playwright MCP.

    This function is designed to be called by Claude Code with Playwright MCP configured.
    It provides instructions for the extraction process.

    Args:
        limit: Maximum number of posts to extract (default 20)

    Returns:
        Dict with extraction results:
        - success: bool
        - extracted: int (number of posts extracted)
        - stored: int (number of new posts stored)
        - skipped: int (number of duplicates skipped)
        - posts: list of extracted post data
        - instructions: extraction instructions for Claude Code
    """
    # This function returns instructions for Claude Code to execute
    # The actual extraction uses Playwright MCP tools

    instructions = f"""
To extract tweets from the Twitter timeline, use the Playwright MCP tools:

1. Navigate to Twitter:
   mcp__playwright__browser_navigate(url="https://twitter.com/home")

2. Wait for the page to load:
   mcp__playwright__browser_wait_for(time=3)

3. Take a snapshot to see the timeline:
   mcp__playwright__browser_snapshot()

4. For each tweet visible, extract:
   - post_id: The tweet's unique ID (from the URL or data attributes)
   - author_name: Display name of the author
   - author_handle: @username of the author
   - content: The tweet text
   - engagement: likes, retweets, replies count if visible

5. Scroll to load more tweets:
   mcp__playwright__browser_press_key(key="PageDown")
   mcp__playwright__browser_wait_for(time=2)

6. Repeat steps 3-5 until you have {limit} tweets

7. For each extracted tweet, store it:
   from twitter import store_extracted_post
   store_extracted_post(post_id, author_name, author_handle, content, engagement)

NOTE: You must be logged into Twitter for this to work.
Use --user-data-dir with Playwright MCP to persist login sessions.
"""

    return {
        "success": True,
        "message": "Feed extraction requires Playwright MCP. See instructions.",
        "instructions": instructions,
        "extracted": 0,
        "stored": 0,
        "skipped": 0,
        "posts": []
    }


def store_extracted_post(
    post_id: str,
    author_name: Optional[str] = None,
    author_handle: Optional[str] = None,
    content: Optional[str] = None,
    content_url: Optional[str] = None,
    engagement: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Store an extracted tweet in the social_feed table.

    Args:
        post_id: Twitter's unique post ID
        author_name: Display name (@DisplayName)
        author_handle: Handle without @ (username)
        content: Tweet text
        content_url: URL to the tweet
        engagement: Dict with likes, retweets, replies, etc.

    Returns:
        Dict with storage result (success, db_id, is_new)
    """
    # Check if already exists
    if post_exists("twitter", post_id):
        return {
            "success": True,
            "is_new": False,
            "message": f"Post {post_id} already exists"
        }

    # Generate URL if not provided
    if not content_url and author_handle and post_id:
        content_url = f"https://twitter.com/{author_handle}/status/{post_id}"

    # Store via social_feed
    db_id = store_post(
        platform="twitter",
        post_id=post_id,
        author_name=author_name,
        author_handle=author_handle,
        content=content,
        content_url=content_url,
        engagement=engagement
    )

    return {
        "success": True,
        "is_new": True,
        "db_id": db_id,
        "message": f"Stored tweet {post_id} with DB ID {db_id}"
    }


def parse_tweet_from_snapshot(snapshot_text: str) -> List[Dict[str, Any]]:
    """
    Parse tweet data from a Playwright browser snapshot.

    This is a helper function to extract tweet information from
    the accessibility tree returned by browser_snapshot.

    Args:
        snapshot_text: The text output from browser_snapshot

    Returns:
        List of parsed tweet dicts with post_id, author, content, etc.
    """
    tweets = []

    # Pattern to match tweet-like content in snapshot
    # This will need refinement based on actual snapshot format
    # Twitter's structure includes article elements with tweet data

    # Look for patterns like:
    # - @username
    # - Tweet content
    # - Engagement numbers (likes, retweets)

    lines = snapshot_text.split('\n')
    current_tweet = {}

    for line in lines:
        line = line.strip()

        # Look for @handle patterns
        handle_match = re.search(r'@(\w+)', line)
        if handle_match and 'author_handle' not in current_tweet:
            current_tweet['author_handle'] = handle_match.group(1)

        # Look for engagement numbers (e.g., "123 Likes", "45 Retweets")
        likes_match = re.search(r'(\d+)\s*(Likes?|likes?)', line)
        retweets_match = re.search(r'(\d+)\s*(Retweets?|retweets?)', line)
        replies_match = re.search(r'(\d+)\s*(Repl(?:y|ies)|repl(?:y|ies))', line)

        if likes_match or retweets_match or replies_match:
            if 'engagement' not in current_tweet:
                current_tweet['engagement'] = {}
            if likes_match:
                current_tweet['engagement']['likes'] = int(likes_match.group(1))
            if retweets_match:
                current_tweet['engagement']['retweets'] = int(retweets_match.group(1))
            if replies_match:
                current_tweet['engagement']['replies'] = int(replies_match.group(1))

        # Look for status URL patterns to get post_id
        url_match = re.search(r'/status/(\d+)', line)
        if url_match:
            current_tweet['post_id'] = url_match.group(1)
            # If we have a post_id, we likely have a complete tweet
            if current_tweet.get('author_handle'):
                tweets.append(current_tweet)
                current_tweet = {}

    return tweets


# ============================================================================
# Relevance Scoring Functions
# ============================================================================

def update_post_score(
    db_id: int,
    relevance_score: float,
    suggested_action: Optional[str] = None
) -> bool:
    """
    Update the relevance score and suggested action for a post.

    Args:
        db_id: Database ID of the post
        relevance_score: Score between 0.0 and 1.0
        suggested_action: Optional action suggestion (reply/quote/dm/like/ignore)

    Returns:
        True if updated, False if post not found
    """
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE social_feed
        SET relevance_score = ?, suggested_action = ?
        WHERE id = ?
    """, (relevance_score, suggested_action, db_id))

    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return updated


def score_relevance(post: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score a post's relevance for engagement using Claude.

    Based on the user's X Operating Manual, evaluates:
    1. Is the author in the user's target audience?
       - AI for science researchers with engineering taste
       - HPC, scientific computing, data infra engineers
       - Lab automation and autonomous experimentation operators
       - Hard tech founders and early employees
       - Defense and energy program people
       - Deep tech investors with full stack instincts

    2. Does the post warrant engagement per the rules?
       - Reply should add missing system detail
       - Reply should ask a pointed question
       - Reply should clarify a technical distinction
       - Be useful, build relationships

    Returns scores 0-1. Only posts scoring > 0.9 (top 0.01%) should be surfaced.

    Args:
        post: Dict with post data (content, author_handle, author_name, engagement)

    Returns:
        Dict with:
        - score: float 0-1
        - audience_match: bool (is author in target audience)
        - engagement_fit: bool (does engagement make sense per rules)
        - reasoning: str (brief explanation)
        - suggested_action: str (reply/quote/dm/like/ignore/None)
    """
    content = post.get('content', '')
    author_handle = post.get('author_handle', '')
    author_name = post.get('author_name', '')
    engagement = post.get('engagement', {})

    # Build prompt for Claude
    prompt = f"""Evaluate this Twitter post for engagement relevance.

CONTEXT: See the user's X Operating Manual in personal/x_operating_manual.md for profile context.

TARGET AUDIENCE (score HIGH if author appears to be):
- Researchers and engineers in the user's field
- People working on related technical problems
- Potential collaborators or thought leaders

AVOID (score LOW if this seems like):
- Generic hype accounts
- Engagement farmers
- Content unrelated to the user's interests

ENGAGEMENT RULES (score HIGH if the user could):
- Add a missing technical detail
- Ask a pointed, specific question
- Clarify a technical distinction
- Provide domain-specific insight
- Build a useful relationship with someone in target audience

POST TO EVALUATE:
Author: {author_name} (@{author_handle})
Content: {content}
Engagement: {json.dumps(engagement) if engagement else 'N/A'}

Respond with JSON only:
{{
  "score": <float 0.0-1.0, be VERY selective - only top 0.01% should score > 0.9>,
  "audience_match": <true/false - is author likely in target audience>,
  "engagement_fit": <true/false - could the user add value per the rules>,
  "reasoning": "<1-2 sentence explanation>",
  "suggested_action": "<reply/quote/like/ignore or null>"
}}

IMPORTANT: Be extremely selective. Most posts should score < 0.3.
Only posts where the user could add real technical value to someone in the target audience should score > 0.9.
"""

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "json", "--max-turns", "1"],
            capture_output=True, text=True, timeout=60,
            cwd="/workspace" if os.path.exists("/workspace") else os.path.dirname(VAULT_PATH)
        )

        # Parse the response
        response = json.loads(result.stdout)

        # Handle Claude's response format
        if isinstance(response, dict) and "result" in response:
            result_text = response["result"]
            # Extract JSON from markdown code block if present
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            parsed = json.loads(result_text)
        else:
            parsed = response

        # Validate and normalize the response
        score = float(parsed.get('score', 0.0))
        score = max(0.0, min(1.0, score))  # Clamp to 0-1

        return {
            "score": score,
            "audience_match": bool(parsed.get('audience_match', False)),
            "engagement_fit": bool(parsed.get('engagement_fit', False)),
            "reasoning": str(parsed.get('reasoning', '')),
            "suggested_action": parsed.get('suggested_action')
        }

    except subprocess.TimeoutExpired:
        return {
            "score": 0.0,
            "audience_match": False,
            "engagement_fit": False,
            "reasoning": "Scoring timed out",
            "suggested_action": None
        }
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return {
            "score": 0.0,
            "audience_match": False,
            "engagement_fit": False,
            "reasoning": f"Failed to parse scoring response: {str(e)}",
            "suggested_action": None
        }
    except FileNotFoundError:
        return {
            "score": 0.0,
            "audience_match": False,
            "engagement_fit": False,
            "reasoning": "Claude CLI not available",
            "suggested_action": None
        }


def score_feed(min_score: float = 0.9) -> List[Dict[str, Any]]:
    """
    Score all unscored posts in the feed and return high-relevance posts.

    Only returns posts scoring above min_score (default 0.9 = top 0.01%).

    Args:
        min_score: Minimum score to include in results (default 0.9)

    Returns:
        List of high-relevance posts with their scores
    """
    try:
        from social_feed import get_unactioned_posts
    except ImportError:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from social_feed import get_unactioned_posts

    # Get posts that haven't been actioned and don't have a score
    unactioned = get_unactioned_posts(platform="twitter")

    high_relevance = []

    for post in unactioned:
        # Skip if already scored
        if post.get('relevance_score') is not None:
            if post['relevance_score'] >= min_score:
                high_relevance.append(post)
            continue

        # Score the post
        result = score_relevance(post)

        # Update the database with the score
        update_post_score(
            db_id=post['id'],
            relevance_score=result['score'],
            suggested_action=result.get('suggested_action')
        )

        # Add to results if high relevance
        if result['score'] >= min_score:
            post['relevance_score'] = result['score']
            post['suggested_action'] = result.get('suggested_action')
            post['scoring_result'] = result
            high_relevance.append(post)

    return high_relevance


def get_high_relevance_posts(min_score: float = 0.9) -> List[Dict[str, Any]]:
    """
    Get posts that have already been scored above the threshold.

    Args:
        min_score: Minimum relevance score (default 0.9)

    Returns:
        List of high-relevance posts
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, platform, post_id, author_name, author_handle,
               content, content_url, engagement,
               relevance_score, suggested_action, action_taken, captured_at
        FROM social_feed
        WHERE platform = 'twitter'
          AND relevance_score >= ?
          AND action_taken IS NULL
        ORDER BY relevance_score DESC, captured_at DESC
    """, (min_score,))

    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        post = dict(row)
        if post.get('engagement'):
            try:
                post['engagement'] = json.loads(post['engagement'])
            except (json.JSONDecodeError, TypeError):
                post['engagement'] = {}
        results.append(post)

    return results


# ============================================================================
# Draft Creation Functions (NO AUTO-POSTING)
# ============================================================================

def draft_reply(post_id: int, suggested_text: str) -> Dict[str, Any]:
    """
    Create a draft reply to a post.

    IMPORTANT: This only creates a draft. It does NOT post anything.
    the user must review and manually post approved drafts.

    Args:
        post_id: Database ID of the post to reply to
        suggested_text: The suggested reply text

    Returns:
        Dict with draft_id and status
    """
    # Verify the post exists
    post = get_post(post_id)
    if not post:
        return {
            "success": False,
            "error": f"Post {post_id} not found"
        }

    draft_id = store_draft(
        draft_type="reply",
        draft_text=suggested_text,
        post_id=post_id
    )

    return {
        "success": True,
        "draft_id": draft_id,
        "draft_type": "reply",
        "target_post": post.get('content', '')[:50],
        "message": "Draft reply created. the user must review and post manually."
    }


def draft_quote(post_id: int, suggested_text: str) -> Dict[str, Any]:
    """
    Create a draft quote tweet.

    IMPORTANT: This only creates a draft. It does NOT post anything.
    the user must review and manually post approved drafts.

    Args:
        post_id: Database ID of the post to quote
        suggested_text: The suggested quote tweet text

    Returns:
        Dict with draft_id and status
    """
    # Verify the post exists
    post = get_post(post_id)
    if not post:
        return {
            "success": False,
            "error": f"Post {post_id} not found"
        }

    draft_id = store_draft(
        draft_type="quote",
        draft_text=suggested_text,
        post_id=post_id
    )

    return {
        "success": True,
        "draft_id": draft_id,
        "draft_type": "quote",
        "target_post": post.get('content', '')[:50],
        "message": "Draft quote tweet created. the user must review and post manually."
    }


def draft_dm(handle: str, suggested_text: str) -> Dict[str, Any]:
    """
    Create a draft DM.

    IMPORTANT: This only creates a draft. It does NOT send anything.
    the user must review and manually send approved DMs.

    Args:
        handle: @handle of the person to DM (without @)
        suggested_text: The suggested DM text

    Returns:
        Dict with draft_id and status
    """
    # Clean handle (remove @ if present)
    handle = handle.lstrip('@')

    draft_id = store_draft(
        draft_type="dm",
        draft_text=suggested_text,
        target_handle=handle
    )

    return {
        "success": True,
        "draft_id": draft_id,
        "draft_type": "dm",
        "target_handle": handle,
        "message": "Draft DM created. the user must review and send manually."
    }


# ============================================================================
# CLI
# ============================================================================

def _format_draft_summary(draft: Dict[str, Any]) -> str:
    """Format a draft for display."""
    draft_type = draft.get('draft_type', 'unknown')
    text = draft.get('draft_text', '')[:60]
    text = text.replace('\n', ' ')

    target = ""
    if draft.get('target_handle'):
        target = f" -> @{draft['target_handle']}"
    elif draft.get('author_handle'):
        target = f" -> @{draft['author_handle']}"

    return f"[{draft['id']}] {draft_type}{target}: {text}..."


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="PCP Twitter Agent - Feed extraction and draft management"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # extract command
    extract_parser = subparsers.add_parser("extract", help="Extract posts from Twitter timeline")
    extract_parser.add_argument("--limit", "-n", type=int, default=20, help="Number of posts to extract (default: 20)")

    # store command (for manual testing)
    store_parser = subparsers.add_parser("store", help="Store an extracted tweet")
    store_parser.add_argument("post_id", help="Twitter post ID")
    store_parser.add_argument("--author", help="Author display name")
    store_parser.add_argument("--handle", help="Author handle (without @)")
    store_parser.add_argument("--content", help="Tweet content")

    # score-feed command
    score_parser = subparsers.add_parser("score-feed", help="Score unscored posts and show high-relevance ones")
    score_parser.add_argument("--min-score", "-m", type=float, default=0.9,
                              help="Minimum score to show (default: 0.9 = top 0.01%%)")
    score_parser.add_argument("--show-all", action="store_true",
                              help="Show all scored posts, not just high-relevance")

    # score-post command (score a single post)
    score_post_parser = subparsers.add_parser("score-post", help="Score a single post by database ID")
    score_post_parser.add_argument("db_id", type=int, help="Database ID of the post to score")

    # high-relevance command (show already-scored high posts)
    high_parser = subparsers.add_parser("high-relevance", help="Show high-relevance posts (already scored)")
    high_parser.add_argument("--min-score", "-m", type=float, default=0.9,
                             help="Minimum score (default: 0.9)")

    # drafts command
    drafts_parser = subparsers.add_parser("drafts", help="List pending drafts")

    # draft-reply command
    reply_parser = subparsers.add_parser("draft-reply", help="Create a draft reply")
    reply_parser.add_argument("post_id", type=int, help="Database ID of post to reply to")
    reply_parser.add_argument("text", help="Draft reply text")

    # draft-quote command
    quote_parser = subparsers.add_parser("draft-quote", help="Create a draft quote tweet")
    quote_parser.add_argument("post_id", type=int, help="Database ID of post to quote")
    quote_parser.add_argument("text", help="Draft quote text")

    # draft-dm command
    dm_parser = subparsers.add_parser("draft-dm", help="Create a draft DM")
    dm_parser.add_argument("handle", help="@handle to DM (without @)")
    dm_parser.add_argument("text", help="Draft DM text")

    # approve command
    approve_parser = subparsers.add_parser("approve", help="Approve a draft")
    approve_parser.add_argument("draft_id", type=int, help="ID of draft to approve")

    # reject command
    reject_parser = subparsers.add_parser("reject", help="Reject a draft")
    reject_parser.add_argument("draft_id", type=int, help="ID of draft to reject")

    args = parser.parse_args()

    if args.command == "extract":
        result = extract_feed(limit=args.limit)
        print(result["message"])
        print("\n" + result["instructions"])

    elif args.command == "store":
        result = store_extracted_post(
            post_id=args.post_id,
            author_name=args.author,
            author_handle=args.handle,
            content=args.content
        )
        if result["is_new"]:
            print(f"Stored tweet with DB ID: {result['db_id']}")
        else:
            print(result["message"])

    elif args.command == "score-feed":
        print("Scoring unscored posts (this may take a while)...")
        if args.show_all:
            # Just show all posts that need scoring, without threshold
            high_relevance = score_feed(min_score=0.0)
            print(f"\nScored {len(high_relevance)} posts:")
            for post in high_relevance:
                handle = post.get('author_handle', 'unknown')
                content = (post.get('content') or '')[:50].replace('\n', ' ')
                score = post.get('relevance_score', 0)
                action = post.get('suggested_action', 'none')
                print(f"  [{post['id']}] @{handle}: {content}...")
                print(f"       Score: {score:.2f} | Action: {action}")
        else:
            high_relevance = score_feed(min_score=args.min_score)
            if high_relevance:
                print(f"\nFound {len(high_relevance)} high-relevance posts (score >= {args.min_score}):")
                for post in high_relevance:
                    handle = post.get('author_handle', 'unknown')
                    content = (post.get('content') or '')[:50].replace('\n', ' ')
                    score = post.get('relevance_score', 0)
                    action = post.get('suggested_action', 'none')
                    reasoning = post.get('scoring_result', {}).get('reasoning', '')
                    print(f"\n  [{post['id']}] @{handle}: {content}...")
                    print(f"       Score: {score:.2f} | Suggested: {action}")
                    if reasoning:
                        print(f"       Reason: {reasoning}")
            else:
                print(f"\nNo posts scored >= {args.min_score} (top 0.01%)")
                print("This is expected - most posts should not meet this threshold.")

    elif args.command == "score-post":
        post = get_post(args.db_id)
        if not post:
            print(f"Post {args.db_id} not found")
        else:
            print(f"Scoring post {args.db_id}...")
            result = score_relevance(post)
            update_post_score(args.db_id, result['score'], result.get('suggested_action'))
            print(f"\nScore: {result['score']:.2f}")
            print(f"Audience Match: {result['audience_match']}")
            print(f"Engagement Fit: {result['engagement_fit']}")
            print(f"Suggested Action: {result.get('suggested_action', 'none')}")
            print(f"Reasoning: {result['reasoning']}")

    elif args.command == "high-relevance":
        posts = get_high_relevance_posts(min_score=args.min_score)
        if posts:
            print(f"Found {len(posts)} high-relevance posts (score >= {args.min_score}):")
            for post in posts:
                handle = post.get('author_handle', 'unknown')
                content = (post.get('content') or '')[:50].replace('\n', ' ')
                score = post.get('relevance_score', 0)
                action = post.get('suggested_action', 'none')
                print(f"  [{post['id']}] @{handle} (score: {score:.2f}, action: {action})")
                print(f"       {content}...")
        else:
            print(f"No high-relevance posts found (score >= {args.min_score})")

    elif args.command == "drafts":
        drafts = get_pending_drafts()
        if drafts:
            print(f"Found {len(drafts)} pending drafts:")
            for draft in drafts:
                print(_format_draft_summary(draft))
        else:
            print("No pending drafts")

    elif args.command == "draft-reply":
        result = draft_reply(args.post_id, args.text)
        if result["success"]:
            print(f"Created draft reply (ID: {result['draft_id']})")
            print("NOTE: This is a DRAFT - the user must review and post manually.")
        else:
            print(f"Error: {result['error']}")

    elif args.command == "draft-quote":
        result = draft_quote(args.post_id, args.text)
        if result["success"]:
            print(f"Created draft quote (ID: {result['draft_id']})")
            print("NOTE: This is a DRAFT - the user must review and post manually.")
        else:
            print(f"Error: {result['error']}")

    elif args.command == "draft-dm":
        result = draft_dm(args.handle, args.text)
        if result["success"]:
            print(f"Created draft DM to @{result['target_handle']} (ID: {result['draft_id']})")
            print("NOTE: This is a DRAFT - the user must review and send manually.")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")

    elif args.command == "approve":
        if approve_draft(args.draft_id):
            print(f"Approved draft {args.draft_id}")
            print("NOTE: the user must still manually post/send this content.")
        else:
            print(f"Draft {args.draft_id} not found")

    elif args.command == "reject":
        if reject_draft(args.draft_id):
            print(f"Rejected draft {args.draft_id}")
        else:
            print(f"Draft {args.draft_id} not found")

    else:
        parser.print_help()
