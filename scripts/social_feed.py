#!/usr/bin/env python3
"""
PCP Social Feed - Platform-agnostic social media content storage.

Stores posts from Twitter, LinkedIn, Mastodon, etc. for:
- Tracking posts to potentially engage with
- Recording engagement actions taken
- Scoring relevance for priority filtering
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

# Support both container and local development paths
VAULT_PATH = "/workspace/vault/vault.db"
if not os.path.exists(os.path.dirname(VAULT_PATH)) and os.path.exists(os.path.join(os.environ.get("PCP_DIR", "/workspace"), "vault")):
    VAULT_PATH = os.path.join(os.environ.get("PCP_DIR", "/workspace"), "vault/vault.db")


# ============================================================================
# Helper Functions
# ============================================================================

def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a sqlite3.Row to a dictionary with proper JSON parsing."""
    result = dict(row)
    # Parse JSON fields
    if result.get('engagement'):
        try:
            result['engagement'] = json.loads(result['engagement'])
        except (json.JSONDecodeError, TypeError):
            result['engagement'] = {}
    return result


# ============================================================================
# Store Functions
# ============================================================================

def store_post(
    platform: str,
    post_id: str,
    author_name: Optional[str] = None,
    author_handle: Optional[str] = None,
    content: Optional[str] = None,
    content_url: Optional[str] = None,
    engagement: Optional[Dict[str, Any]] = None,
    relevance_score: Optional[float] = None,
    suggested_action: Optional[str] = None
) -> int:
    """
    Store a social media post in the database.

    Args:
        platform: Platform name (twitter, linkedin, mastodon, etc.)
        post_id: Platform-specific post ID
        author_name: Display name of the author
        author_handle: @handle or username
        content: Post text/content
        content_url: URL to original post
        engagement: Dict with engagement metrics (likes, retweets, etc.)
        relevance_score: 0.0 to 1.0 relevance score
        suggested_action: Suggested action (reply/quote/dm/like/ignore)

    Returns:
        The ID of the created/existing post entry
    """
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    # Check if post already exists
    cursor.execute("""
        SELECT id FROM social_feed
        WHERE platform = ? AND post_id = ?
    """, (platform, post_id))

    existing = cursor.fetchone()
    if existing:
        conn.close()
        return existing[0]

    # Insert new post
    cursor.execute("""
        INSERT INTO social_feed (
            platform, post_id, author_name, author_handle,
            content, content_url, engagement,
            relevance_score, suggested_action, captured_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        platform,
        post_id,
        author_name,
        author_handle,
        content,
        content_url,
        json.dumps(engagement) if engagement else None,
        relevance_score,
        suggested_action,
        datetime.now().isoformat()
    ))

    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return new_id


def get_post(post_id_or_db_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a post by its database ID.

    Args:
        post_id_or_db_id: The database ID of the post

    Returns:
        Dict with post details or None if not found
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, platform, post_id, author_name, author_handle,
               content, content_url, engagement,
               relevance_score, suggested_action, action_taken, captured_at
        FROM social_feed
        WHERE id = ?
    """, (post_id_or_db_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return _row_to_dict(row)


def post_exists(platform: str, post_id: str) -> bool:
    """
    Check if a post already exists in the database.

    Args:
        platform: Platform name (twitter, linkedin, etc.)
        post_id: Platform-specific post ID

    Returns:
        True if post exists, False otherwise
    """
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 1 FROM social_feed
        WHERE platform = ? AND post_id = ?
    """, (platform, post_id))

    exists = cursor.fetchone() is not None
    conn.close()

    return exists


# ============================================================================
# Query Functions
# ============================================================================

def list_posts(
    platform: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    List recent posts, optionally filtered by platform.

    Args:
        platform: Optional platform filter (twitter, linkedin, etc.)
        limit: Maximum number of posts to return (default 50)

    Returns:
        List of post dicts, ordered by captured_at DESC (most recent first)
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT id, platform, post_id, author_name, author_handle,
               content, content_url, engagement,
               relevance_score, suggested_action, action_taken, captured_at
        FROM social_feed
        WHERE 1=1
    """
    params = []

    if platform:
        query += " AND platform = ?"
        params.append(platform)

    query += " ORDER BY captured_at DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [_row_to_dict(row) for row in rows]


def get_unactioned_posts(
    platform: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get posts that haven't had an action taken yet.

    Args:
        platform: Optional platform filter

    Returns:
        List of unactioned post dicts, ordered by relevance_score DESC then captured_at DESC
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT id, platform, post_id, author_name, author_handle,
               content, content_url, engagement,
               relevance_score, suggested_action, action_taken, captured_at
        FROM social_feed
        WHERE action_taken IS NULL
    """
    params = []

    if platform:
        query += " AND platform = ?"
        params.append(platform)

    # Order by relevance score (high scores first), then by recency
    query += " ORDER BY COALESCE(relevance_score, 0) DESC, captured_at DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [_row_to_dict(row) for row in rows]


def search_posts(query: str) -> List[Dict[str, Any]]:
    """
    Search posts by content, author name, or handle.

    Args:
        query: Search query string

    Returns:
        List of matching post dicts, ordered by relevance_score DESC then captured_at DESC
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    search_pattern = f"%{query}%"

    cursor.execute("""
        SELECT id, platform, post_id, author_name, author_handle,
               content, content_url, engagement,
               relevance_score, suggested_action, action_taken, captured_at
        FROM social_feed
        WHERE content LIKE ?
           OR author_name LIKE ?
           OR author_handle LIKE ?
        ORDER BY COALESCE(relevance_score, 0) DESC, captured_at DESC
    """, (search_pattern, search_pattern, search_pattern))

    rows = cursor.fetchall()
    conn.close()

    return [_row_to_dict(row) for row in rows]


def update_action(post_id: int, action_taken: str) -> bool:
    """
    Record the action taken on a post.

    Args:
        post_id: Database ID of the post
        action_taken: Description of action taken (e.g., "replied", "liked", "ignored")

    Returns:
        True if post was updated, False if post not found
    """
    # Check if post exists
    if not get_post(post_id):
        return False

    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE social_feed
        SET action_taken = ?
        WHERE id = ?
    """, (action_taken, post_id))

    conn.commit()
    conn.close()

    return True


# ============================================================================
# CLI
# ============================================================================

def _format_post_summary(post: Dict[str, Any]) -> str:
    """Format a post for list display."""
    author = post.get('author_handle') or post.get('author_name') or 'Unknown'
    content = post.get('content') or ''
    # Truncate content to 60 chars for display
    content_preview = content[:60] + '...' if len(content) > 60 else content
    content_preview = content_preview.replace('\n', ' ')

    score = post.get('relevance_score')
    score_str = f" [score:{score:.2f}]" if score else ""

    action = post.get('action_taken')
    action_str = f" ✓{action}" if action else ""

    return f"[{post['id']}] {post['platform']}: @{author} - {content_preview}{score_str}{action_str}"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="PCP Social Feed - Store and query social media content"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # store command
    store_parser = subparsers.add_parser("store", help="Store a post")
    store_parser.add_argument("platform", help="Platform (twitter, linkedin, etc.)")
    store_parser.add_argument("post_id", help="Platform-specific post ID")
    store_parser.add_argument("--author", help="Author display name")
    store_parser.add_argument("--handle", help="Author handle (@username)")
    store_parser.add_argument("--content", help="Post content")
    store_parser.add_argument("--url", help="URL to original post")

    # get command
    get_parser = subparsers.add_parser("get", help="Get a post by database ID")
    get_parser.add_argument("id", type=int, help="Database ID of the post")

    # exists command
    exists_parser = subparsers.add_parser("exists", help="Check if a post exists")
    exists_parser.add_argument("platform", help="Platform (twitter, linkedin, etc.)")
    exists_parser.add_argument("post_id", help="Platform-specific post ID")

    # list command
    list_parser = subparsers.add_parser("list", help="List recent posts")
    list_parser.add_argument("--platform", "-p", help="Filter by platform (twitter, linkedin, etc.)")
    list_parser.add_argument("--limit", "-n", type=int, default=50, help="Maximum posts to show (default: 50)")

    # unactioned command
    unactioned_parser = subparsers.add_parser("unactioned", help="List posts needing action")
    unactioned_parser.add_argument("--platform", "-p", help="Filter by platform")

    # search command
    search_parser = subparsers.add_parser("search", help="Search posts by content/author")
    search_parser.add_argument("query", help="Search query string")

    # action command
    action_parser = subparsers.add_parser("action", help="Record an action taken on a post")
    action_parser.add_argument("id", type=int, help="Database ID of the post")
    action_parser.add_argument("action_taken", help="Description of action (replied, liked, ignored, etc.)")

    args = parser.parse_args()

    if args.command == "store":
        result_id = store_post(
            platform=args.platform,
            post_id=args.post_id,
            author_name=args.author,
            author_handle=args.handle,
            content=args.content,
            content_url=args.url
        )
        print(f"Stored post with ID: {result_id}")

    elif args.command == "get":
        post = get_post(args.id)
        if post:
            print(f"Platform: {post['platform']}")
            print(f"Post ID: {post['post_id']}")
            print(f"Author: {post['author_name']} (@{post['author_handle']})")
            print(f"Content: {post['content']}")
            if post.get('engagement'):
                print(f"Engagement: {post['engagement']}")
            if post.get('relevance_score'):
                print(f"Relevance: {post['relevance_score']}")
            if post.get('suggested_action'):
                print(f"Suggested: {post['suggested_action']}")
            if post.get('action_taken'):
                print(f"Action Taken: {post['action_taken']}")
        else:
            print(f"No post found with ID {args.id}")

    elif args.command == "exists":
        exists = post_exists(args.platform, args.post_id)
        if exists:
            print(f"Post {args.platform}:{args.post_id} exists")
        else:
            print(f"Post {args.platform}:{args.post_id} does not exist")

    elif args.command == "list":
        posts = list_posts(platform=args.platform, limit=args.limit)
        if posts:
            print(f"Found {len(posts)} posts:")
            for post in posts:
                print(_format_post_summary(post))
        else:
            print("No posts found")

    elif args.command == "unactioned":
        posts = get_unactioned_posts(platform=args.platform)
        if posts:
            print(f"Found {len(posts)} posts needing action:")
            for post in posts:
                print(_format_post_summary(post))
        else:
            print("No unactioned posts found")

    elif args.command == "search":
        posts = search_posts(args.query)
        if posts:
            print(f"Found {len(posts)} matching posts:")
            for post in posts:
                print(_format_post_summary(post))
        else:
            print(f"No posts found matching '{args.query}'")

    elif args.command == "action":
        success = update_action(args.id, args.action_taken)
        if success:
            print(f"Recorded action '{args.action_taken}' on post {args.id}")
        else:
            print(f"Post {args.id} not found")

    else:
        parser.print_help()
