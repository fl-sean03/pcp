"""
Moltbook Fleet Client for PCP

Thin wrapper around the moltbook-fleet REST API.
"""

import httpx
from typing import Optional, List, Dict, Any

FLEET_URL = "http://moltbook-fleet:8200/api/v1"
TIMEOUT = 30.0


class MoltbookFleetError(Exception):
    """Error from Moltbook Fleet API."""
    pass


async def _request(
    method: str,
    endpoint: str,
    json: Optional[Dict] = None,
    params: Optional[Dict] = None
) -> Dict[str, Any]:
    """Make request to fleet API."""
    url = f"{FLEET_URL}{endpoint}"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.request(method, url, json=json, params=params)

        if response.status_code >= 400:
            try:
                error = response.json().get("detail", response.text)
            except:
                error = response.text
            raise MoltbookFleetError(f"Fleet API error ({response.status_code}): {error}")

        return response.json()


# Agent Management

async def create_agent(
    name: str,
    description: str,
    persona: str,
    focus_topics: List[str] = None,
    tone: str = "neutral",
    heartbeat_hours: int = 0,
    auto_actions: List[str] = None
) -> Dict[str, Any]:
    """
    Create a new Moltbook agent.

    Args:
        name: Display name on Moltbook (unique)
        description: Short description for Moltbook profile
        persona: System prompt defining agent's behavior/voice
        focus_topics: List of topics agent cares about
        tone: Writing style (neutral, formal, casual, enthusiastic, sarcastic)
        heartbeat_hours: Auto-engage interval (0 = manual only)
        auto_actions: Actions to perform on heartbeat (browse, vote)

    Returns:
        {id, name, status, claim_url, claim_code, instructions}

    Note: User must post claim_code to Twitter/X to verify ownership.
    """
    return await _request("POST", "/agents", json={
        "name": name,
        "description": description,
        "persona": persona,
        "focus_topics": focus_topics or [],
        "tone": tone,
        "heartbeat_hours": heartbeat_hours,
        "auto_actions": auto_actions or []
    })


async def list_agents(status: str = None) -> List[Dict[str, Any]]:
    """
    List all agents.

    Args:
        status: Filter by status (pending_claim, active, suspended)

    Returns:
        List of {id, name, status, karma, posts_count, last_active}
    """
    params = {"status": status} if status else {}
    result = await _request("GET", "/agents", params=params)
    return result.get("agents", [])


async def get_agent(agent_id: str) -> Dict[str, Any]:
    """
    Get full agent details.

    Returns:
        Complete agent object including persona, stats, history
    """
    return await _request("GET", f"/agents/{agent_id}")


async def update_agent(agent_id: str, **updates) -> Dict[str, Any]:
    """
    Update agent configuration.

    Args:
        agent_id: Agent ID
        **updates: Fields to update (persona, tone, heartbeat_hours, etc.)

    Returns:
        Updated agent object
    """
    return await _request("PATCH", f"/agents/{agent_id}", json=updates)


async def delete_agent(agent_id: str) -> Dict[str, Any]:
    """
    Decommission an agent (soft delete).

    The agent will be marked as suspended but history is preserved.
    """
    return await _request("DELETE", f"/agents/{agent_id}")


async def mark_claimed(agent_id: str) -> Dict[str, Any]:
    """
    Mark agent as claimed/verified.

    Call this after the human has posted the claim code to Twitter.
    """
    return await _request("POST", f"/agents/{agent_id}/claim")


# Agent Actions

async def agent_action(
    agent_id: str,
    action: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Make an agent perform an action.

    Args:
        agent_id: Agent ID
        action: Action type (post, comment, vote, follow, unfollow, browse)
        params: Action-specific parameters

    Returns:
        {success, action_id, result?, error?}
    """
    return await _request("POST", f"/agents/{agent_id}/act", json={
        "action": action,
        "params": params
    })


async def post(
    agent_id: str,
    content: str,
    submolt: str = None,
    url: str = None
) -> Dict[str, Any]:
    """
    Make agent create a post.

    Args:
        agent_id: Agent ID
        content: Post content
        submolt: Community to post in (optional)
        url: Link to include (optional)

    Returns:
        {success, action_id, result: {post_id, url}}
    """
    params = {"content": content}
    if submolt:
        params["submolt"] = submolt
    if url:
        params["url"] = url
    return await agent_action(agent_id, "post", params)


async def comment(
    agent_id: str,
    post_id: str,
    content: str,
    parent_id: str = None
) -> Dict[str, Any]:
    """
    Make agent comment on a post.

    Args:
        agent_id: Agent ID
        post_id: Post to comment on
        content: Comment content
        parent_id: Parent comment ID for replies (optional)

    Returns:
        {success, action_id, result: {comment_id}}
    """
    params = {"post_id": post_id, "content": content}
    if parent_id:
        params["parent_id"] = parent_id
    return await agent_action(agent_id, "comment", params)


async def vote(
    agent_id: str,
    target_type: str,
    target_id: str,
    direction: str = "up"
) -> Dict[str, Any]:
    """
    Make agent vote on a post or comment.

    Args:
        agent_id: Agent ID
        target_type: "post" or "comment"
        target_id: ID of target
        direction: "up" or "down"

    Returns:
        {success, action_id, result}
    """
    return await agent_action(agent_id, "vote", {
        "target_type": target_type,
        "target_id": target_id,
        "direction": direction
    })


async def follow(agent_id: str, target_name: str) -> Dict[str, Any]:
    """Make agent follow another agent."""
    return await agent_action(agent_id, "follow", {"agent_name": target_name})


async def unfollow(agent_id: str, target_name: str) -> Dict[str, Any]:
    """Make agent unfollow another agent."""
    return await agent_action(agent_id, "unfollow", {"agent_name": target_name})


async def browse(
    agent_id: str,
    submolt: str = None,
    auto_engage: bool = False,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Make agent browse feed.

    Args:
        agent_id: Agent ID
        submolt: Specific community (optional)
        auto_engage: Automatically vote on interesting posts
        limit: Number of posts to fetch

    Returns:
        {success, action_id, result: {posts: [...]}}
    """
    return await agent_action(agent_id, "browse", {
        "submolt": submolt,
        "auto_engage": auto_engage,
        "limit": limit
    })


# Feed & Discovery

async def get_feed(
    agent_id: str,
    submolt: str = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Get what the agent sees in their feed.

    Args:
        agent_id: Agent ID
        submolt: Specific community (optional)
        limit: Number of posts

    Returns:
        {posts: [{id, author, content, karma, comments, submolt, created_at}]}
    """
    params = {"limit": limit}
    if submolt:
        params["submolt"] = submolt
    return await _request("GET", f"/agents/{agent_id}/feed", params=params)


async def search(agent_id: str, query: str) -> Dict[str, Any]:
    """
    Search Moltbook as this agent.

    Args:
        agent_id: Agent ID
        query: Search query

    Returns:
        Search results from Moltbook
    """
    return await _request("GET", f"/agents/{agent_id}/search", params={"q": query})


async def get_action_history(
    agent_id: str,
    action_type: str = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get agent's action history.

    Args:
        agent_id: Agent ID
        action_type: Filter by type (post, comment, vote, etc.)
        limit: Number of actions

    Returns:
        List of actions with timestamps and results
    """
    params = {"limit": limit}
    if action_type:
        params["action_type"] = action_type
    result = await _request("GET", f"/agents/{agent_id}/actions", params=params)
    return result.get("actions", [])


# Fleet Management

async def fleet_stats() -> Dict[str, Any]:
    """
    Get fleet-wide statistics.

    Returns:
        {total_agents, active_agents, pending_agents,
         total_karma, total_posts, total_comments, actions_today}
    """
    return await _request("GET", "/stats")


async def fleet_health() -> Dict[str, Any]:
    """
    Check fleet health.

    Returns:
        {status, agents_total, agents_active, moltbook_api, scheduler}
    """
    return await _request("GET", "/health")


async def sync_all_stats() -> Dict[str, Any]:
    """
    Force sync stats from Moltbook for all agents.

    Returns:
        {synced, errors, total}
    """
    return await _request("POST", "/sync")
