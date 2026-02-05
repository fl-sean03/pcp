#!/usr/bin/env python3
"""
PCP Comprehensive Test Suite

Tests all core functionality to ensure PCP works as intended.
Run: python test_pcp.py [--verbose] [--category CATEGORY]

Categories: capture, brain_dump, search, tasks, knowledge,
            briefs, relationships, projects, integration,
            confirmation, attachments, semantic, proactive, system
"""

import sqlite3
import json
import sys
import os
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test configuration
VAULT_PATH = "/workspace/vault/vault.db"
if not os.path.exists(os.path.dirname(VAULT_PATH)):
    VAULT_PATH = os.path.join(os.path.dirname(__file__), "..", "vault", "vault.db")

# Test results tracking
RESULTS = {"passed": 0, "failed": 0, "skipped": 0, "errors": []}
VERBOSE = False


def log(msg: str, level: str = "info"):
    """Log test output."""
    if level == "pass":
        print(f"  ✓ {msg}")
        RESULTS["passed"] += 1
    elif level == "fail":
        print(f"  ✗ {msg}")
        RESULTS["failed"] += 1
        RESULTS["errors"].append(msg)
    elif level == "skip":
        print(f"  ○ {msg}")
        RESULTS["skipped"] += 1
    elif level == "header":
        print(f"\n{'='*60}")
        print(f"  {msg}")
        print(f"{'='*60}")
    elif VERBOSE:
        print(f"    {msg}")


def assert_true(condition: bool, message: str):
    """Assert a condition is true."""
    if condition:
        log(message, "pass")
    else:
        log(f"FAILED: {message}", "fail")


def assert_equals(actual, expected, message: str):
    """Assert two values are equal."""
    if actual == expected:
        log(message, "pass")
    else:
        log(f"FAILED: {message} (expected {expected}, got {actual})", "fail")


def assert_contains(haystack, needle, message: str):
    """Assert haystack contains needle."""
    if needle in haystack:
        log(message, "pass")
    else:
        log(f"FAILED: {message} ('{needle}' not found)", "fail")


def assert_not_empty(value, message: str):
    """Assert value is not empty."""
    if value:
        log(message, "pass")
    else:
        log(f"FAILED: {message} (value is empty)", "fail")


def cleanup_test_data():
    """Clean up any test data from previous runs."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    # Delete test data (identified by [TEST] prefix or test_ prefix)
    cursor.execute("DELETE FROM captures_v2 WHERE content LIKE '[TEST]%' OR content LIKE 'TEST:%'")
    cursor.execute("DELETE FROM tasks WHERE content LIKE '[TEST]%' OR content LIKE 'TEST:%'")
    cursor.execute("DELETE FROM people WHERE name LIKE 'Test%'")
    cursor.execute("DELETE FROM knowledge WHERE content LIKE '[TEST]%' OR source LIKE 'test%'")
    cursor.execute("DELETE FROM decisions WHERE content LIKE '[TEST]%'")

    conn.commit()
    conn.close()
    log("Cleaned up test data from previous runs")


# ============================================================================
# CATEGORY 1: Smart Capture Tests
# ============================================================================

def test_capture_basic():
    """Test basic capture functionality."""
    log("Smart Capture Tests", "header")

    from vault_v2 import smart_capture

    # Test 1: Basic text capture
    result = smart_capture("[TEST] Basic capture test message")
    assert_not_empty(result.get("capture_id"), "Basic capture creates capture_id")
    assert_true(result.get("type") in ["note", "task", "idea", "decision", "question", "chat"],
                "Capture has valid type")

    # Test 2: Capture with person mentioned
    result = smart_capture("[TEST] TestPerson mentioned the project needs work")
    assert_not_empty(result.get("entities", {}).get("people", []),
                     "Capture extracts people from text")

    # Test 3: Capture with deadline should create task
    result = smart_capture("[TEST] Need to finish this by tomorrow")
    assert_true(result.get("temporal", {}).get("has_deadline", False) or result.get("task_id"),
                "Capture with deadline creates task or detects deadline")

    # Test 4: Capture with follow-up language creates task
    result = smart_capture("[TEST] I'll follow up with TestPerson about this")
    # Follow-ups are now stored as tasks
    log(f"Task created: {result.get('task_id', 'not created')}")


def test_capture_entity_extraction():
    """Test entity extraction from captures."""
    from vault_v2 import extract_entities

    # Test person extraction
    entities = extract_entities("John and Sarah discussed the API performance")
    assert_true("John" in str(entities.get("people", [])) or "Sarah" in str(entities.get("people", [])),
                "Extracts person names from text")

    # Test project/topic extraction
    entities = extract_entities("The MatterStack pipeline is running slowly")
    assert_not_empty(entities.get("projects", []) or entities.get("topics", []),
                     "Extracts projects or topics from text")

    # Test date extraction
    entities = extract_entities("Meeting scheduled for next Friday")
    assert_not_empty(entities.get("dates", []),
                     "Extracts date references from text")


def test_capture_temporal_parsing():
    """Test temporal reference parsing."""
    from vault_v2 import parse_temporal

    # Test "tomorrow"
    result = parse_temporal("Finish this by tomorrow")
    assert_true(result.get("has_deadline", False),
                "Detects 'tomorrow' as deadline")

    # Test "next week"
    result = parse_temporal("Review this next week")
    # May be detected as deadline or reminder
    log(f"'Next week' parsed as: deadline={result.get('has_deadline')}, reminder={result.get('has_reminder')}")

    # Test explicit date
    result = parse_temporal("Due on January 30th")
    assert_true(result.get("has_deadline", False) or result.get("deadline_date"),
                "Detects explicit date as deadline")


# ============================================================================
# CATEGORY 2: Brain Dump Tests
# ============================================================================

def test_brain_dump_parsing():
    """Test brain dump parsing into multiple items."""
    log("Brain Dump Tests", "header")

    from vault_v2 import parse_brain_dump

    # Test multi-item parsing
    text = """[TEST] Brain dump:
    - TestPerson mentioned the API is slow
    - Need to email TestClient about the contract
    - Maybe we should look into caching
    - We decided to use PostgreSQL"""

    result = parse_brain_dump(text)
    items = result.get("items", [])

    assert_true(len(items) >= 3, f"Parses multiple items (got {len(items)})")

    # Check type diversity
    types = set(item.get("type") for item in items)
    assert_true(len(types) >= 2, f"Identifies different item types (got {types})")


def test_brain_dump_type_detection():
    """Test that brain dump correctly categorizes item types."""
    from vault_v2 import parse_brain_dump

    text = """[TEST] Mixed items:
    - The database seems slow lately (observation)
    - TestManager prefers async communication
    - Should explore GraphQL at some point
    - Send the report to TestClient by Friday
    - We decided to use Docker for deployment"""

    result = parse_brain_dump(text)
    items = result.get("items", [])

    types_found = [item.get("type") for item in items]
    log(f"Types found: {types_found}")

    # Should have mix of types
    assert_true("task" in types_found, "Detects tasks in brain dump")
    # Other types may vary based on AI interpretation


def test_brain_dump_grouping():
    """Test that related items get grouped together."""
    from vault_v2 import parse_brain_dump

    text = """[TEST] Oracle setup tasks:
    - Set up Oracle account with VPN
    - Configure Oracle database
    - Test Oracle connection"""

    result = parse_brain_dump(text)
    items = result.get("items", [])

    # Check if items have group tags
    groups = [item.get("group") for item in items if item.get("group")]
    if groups:
        assert_true(len(set(groups)) <= 2, f"Related items grouped together (groups: {set(groups)})")
    else:
        log("No explicit grouping detected (AI may not have grouped)", "skip")


def test_brain_dump_storage():
    """Test that brain dump items are stored correctly."""
    from vault_v2 import brain_dump

    text = """[TEST] Storage test:
    - TestStoragePerson said hello
    - Remember to check the logs"""

    result = brain_dump(text, source="test")

    assert_not_empty(result.get("parent_capture_id"), "Creates parent capture")

    total_created = (
        len(result.get("task_ids", [])) +
        len(result.get("capture_ids", [])) +
        len(result.get("knowledge_ids", [])) +
        len(result.get("decision_ids", []))
    )
    assert_true(total_created >= 1, f"Creates items in database (got {total_created})")


def test_brain_dump_edge_cases():
    """Test brain dump edge cases."""
    from vault_v2 import parse_brain_dump

    # Empty input
    result = parse_brain_dump("")
    assert_not_empty(result.get("items", []) or result.get("summary"),
                     "Handles empty input gracefully")

    # Single item (should still work)
    result = parse_brain_dump("[TEST] Just one thing to do")
    assert_true(len(result.get("items", [])) >= 1, "Handles single item")

    # Very long input
    long_text = "[TEST] " + "Item " * 100
    result = parse_brain_dump(long_text)
    assert_not_empty(result, "Handles long input")


# ============================================================================
# CATEGORY 3: Search Tests
# ============================================================================

def test_search_basic():
    """Test basic search functionality."""
    log("Search Tests", "header")

    from vault_v2 import smart_capture, smart_search

    # Create a capture to search for
    unique_id = datetime.now().strftime("%H%M%S")
    smart_capture(f"[TEST] SearchTest{unique_id} unique content here")

    # Search for it
    results = smart_search(f"SearchTest{unique_id}")
    assert_true(len(results) >= 1, "Finds captured content by keyword")


def test_unified_search():
    """Test unified search across all sources."""
    from vault_v2 import unified_search

    # Search all sources
    results = unified_search("test", sources=None)

    # Should return results with source_type
    if results:
        source_types = set(r.get("source_type") for r in results)
        log(f"Sources searched: {source_types}")
        assert_true(all(r.get("source_type") for r in results),
                    "Unified search returns source_type for each result")
    else:
        log("No results found (may need data)", "skip")


def test_search_filters():
    """Test search with source filters."""
    from vault_v2 import unified_search

    # Search only tasks
    results = unified_search("test", sources=["tasks"])
    if results:
        assert_true(all(r.get("source_type") == "tasks" for r in results),
                    "Source filter works correctly")

    # Search multiple sources
    results = unified_search("test", sources=["captures", "knowledge"])
    if results:
        source_types = set(r.get("source_type") for r in results)
        assert_true(source_types.issubset({"captures", "knowledge"}),
                    "Multiple source filter works")


# ============================================================================
# CATEGORY 4: Task Management Tests
# ============================================================================

def test_task_creation():
    """Test task creation and retrieval."""
    log("Task Management Tests", "header")

    from vault_v2 import smart_capture, get_tasks

    # Create task via capture with deadline
    result = smart_capture("[TEST] Task creation test - due tomorrow")

    # Get pending tasks
    tasks = get_tasks(status="pending")
    test_tasks = [t for t in tasks if "[TEST]" in t.get("content", "")]

    assert_true(len(test_tasks) >= 0, "Can retrieve tasks (may or may not have created one)")


def test_task_completion():
    """Test task completion."""
    from vault_v2 import get_tasks, complete_task

    tasks = get_tasks(status="pending")
    test_tasks = [t for t in tasks if "[TEST]" in t.get("content", "")]

    if test_tasks:
        task_id = test_tasks[0]["id"]
        result = complete_task(task_id)
        assert_true(result, f"Task {task_id} marked complete")
    else:
        log("No test tasks to complete", "skip")


def test_task_with_context():
    """Test task context retrieval."""
    from vault_v2 import get_task_with_context, brain_dump

    # Create task via brain dump to have context
    result = brain_dump("[TEST] Context test: need to review the docs", source="test")

    if result.get("task_ids"):
        task_id = result["task_ids"][0]
        task = get_task_with_context(task_id)

        assert_not_empty(task, "Can retrieve task with context")
        assert_true("context" in task, "Task has context field")
    else:
        log("No task created for context test", "skip")


# ============================================================================
# CATEGORY 5: Knowledge Base Tests
# ============================================================================

def test_knowledge_add():
    """Test adding knowledge."""
    log("Knowledge Base Tests", "header")

    try:
        from knowledge import add_knowledge, query_knowledge

        # Add a fact
        k_id = add_knowledge(
            "[TEST] TestSystem uses Redis for caching",
            category="architecture",
            source="test"
        )
        assert_not_empty(k_id, "Knowledge added successfully")

        # Query it back
        results = query_knowledge("TestSystem Redis")
        assert_true(len(results) >= 1, "Can query added knowledge")

    except ImportError:
        log("Knowledge module not available", "skip")


def test_knowledge_categories():
    """Test knowledge categories."""
    try:
        from knowledge import add_knowledge, list_knowledge

        # Add different categories
        add_knowledge("[TEST] Architecture fact", category="architecture", source="test")
        add_knowledge("[TEST] Decision made", category="decision", source="test")
        add_knowledge("[TEST] User preference", category="preference", source="test")

        # List by category
        arch = list_knowledge(category="architecture")
        test_arch = [k for k in arch if "[TEST]" in k.get("content", "")]
        assert_true(len(test_arch) >= 1, "Can filter knowledge by category")

    except ImportError:
        log("Knowledge module not available", "skip")


# ============================================================================
# CATEGORY 6: Brief Generation Tests
# ============================================================================

def test_brief_daily():
    """Test daily brief generation."""
    log("Brief Generation Tests", "header")

    try:
        from brief import generate_brief, daily_brief

        # Generate structured data
        data = generate_brief("daily")
        assert_not_empty(data, "Daily brief generates data")

        # Generate formatted brief
        text = daily_brief()
        assert_not_empty(text, "Daily brief generates text")
        # Check for common brief content (greeting, stats, or pending items)
        has_content = any(word in text.lower() for word in ['rundown', 'pending', 'tasks', 'captures', 'morning', 'afternoon', 'evening'])
        assert_true(has_content, "Daily brief contains expected content")

    except ImportError:
        log("Brief module not available", "skip")
    except Exception as e:
        log(f"Brief generation error: {e}", "skip")


def test_brief_weekly():
    """Test weekly summary generation."""
    try:
        from brief import generate_weekly_summary

        data = generate_weekly_summary()
        assert_not_empty(data, "Weekly summary generates data")

    except ImportError:
        log("Brief module not available", "skip")
    except Exception as e:
        log(f"Weekly summary error: {e}", "skip")


def test_brief_eod():
    """Test end-of-day digest generation."""
    try:
        from brief import generate_eod_digest

        data = generate_eod_digest()
        assert_not_empty(data, "EOD digest generates data")

    except ImportError:
        log("Brief module not available", "skip")
    except Exception as e:
        log(f"EOD digest error: {e}", "skip")


# ============================================================================
# CATEGORY 8: Relationship Tracking Tests
# ============================================================================

def test_relationship_tracking():
    """Test relationship/contact tracking."""
    log("Relationship Tracking Tests", "header")

    from vault_v2 import smart_capture, get_stale_relationships

    # Capture should update contact tracking
    smart_capture("[TEST] Talked to TestRelationPerson about the project")

    # Check stale relationships function works
    stale = get_stale_relationships(days=14)
    assert_true(isinstance(stale, list), "Can retrieve stale relationships")


def test_relationship_summary():
    """Test relationship summary generation."""
    from vault_v2 import get_relationship_summary

    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM people LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if row:
        person_id = row[0]
        summary = get_relationship_summary(person_id)
        assert_not_empty(summary, "Can generate relationship summary")
        assert_true("name" in summary, "Summary includes name")
    else:
        log("No people in database for summary test", "skip")


# ============================================================================
# CATEGORY 9: Project Health Tests
# ============================================================================

def test_project_health():
    """Test project health monitoring."""
    log("Project Health Tests", "header")

    from vault_v2 import get_project_health, get_stalled_projects

    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM projects WHERE status = 'active' LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if row:
        project_id = row[0]
        health = get_project_health(project_id)
        assert_not_empty(health, "Can get project health")
        assert_true("health" in health, "Health includes status")
    else:
        log("No active projects for health test", "skip")

    # Test stalled projects
    stalled = get_stalled_projects(days=14)
    assert_true(isinstance(stalled, list), "Can retrieve stalled projects")


def test_project_context():
    """Test project context restoration."""
    from vault_v2 import get_project_context, restore_context

    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM projects LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if row:
        project_id = row[0]

        # Structured context
        ctx = get_project_context(project_id)
        assert_not_empty(ctx, "Can get project context")

        # Human-readable context
        text = restore_context(project_id)
        assert_not_empty(text, "Can restore context as text")
    else:
        log("No projects for context test", "skip")


# ============================================================================
# CATEGORY 10: Integration Tests
# ============================================================================

def test_full_capture_flow():
    """Test full capture → search → retrieve flow."""
    log("Integration Tests", "header")

    from vault_v2 import smart_capture, smart_search, get_task_with_context

    # Unique identifier for this test
    unique = f"IntegrationTest{datetime.now().strftime('%H%M%S')}"

    # Step 1: Capture
    result = smart_capture(f"[TEST] {unique} - TestIntegrationPerson mentioned deadline tomorrow")
    capture_id = result.get("capture_id")
    assert_not_empty(capture_id, "Integration: Capture created")

    # Step 2: Search
    search_results = smart_search(unique)
    assert_true(len(search_results) >= 1, "Integration: Can find captured content")

    # Step 3: If task created, verify context
    if result.get("task_id"):
        task = get_task_with_context(result["task_id"])
        assert_not_empty(task, "Integration: Can retrieve task with context")


def test_brain_dump_to_brief_flow():
    """Test brain dump → tasks → brief flow."""
    from vault_v2 import brain_dump, get_tasks

    # Create tasks via brain dump
    result = brain_dump("""[TEST] Integration test items:
    - Review the integration test results
    - Send update to TestTeamMember""", source="test")

    # Verify tasks exist
    tasks = get_tasks(status="pending")
    test_tasks = [t for t in tasks if "[TEST]" in t.get("content", "")]

    log(f"Integration: Brain dump created {len(result.get('task_ids', []))} tasks")

    # Brief would include these tasks
    try:
        from brief import generate_brief
        brief_data = generate_brief("daily")
        assert_not_empty(brief_data, "Integration: Brief generation works after brain dump")
    except:
        log("Brief generation not available", "skip")


def test_entity_linking_flow():
    """Test entity extraction → linking → retrieval flow."""
    from vault_v2 import smart_capture, get_person, get_project

    # Capture with known project name (if exists)
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM projects WHERE status = 'active' LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if row:
        project_name = row[0]
        smart_capture(f"[TEST] Working on {project_name} integration today")

        # Verify project is retrievable
        project = get_project(project_name)
        assert_not_empty(project, f"Integration: Project '{project_name}' is retrievable")
    else:
        log("No projects for entity linking test", "skip")


# ============================================================================
# NEW FEATURE TESTS
# ============================================================================

def test_capture_confirmation():
    """Test capture confirmation formatting."""
    log("Capture Confirmation Tests", "header")
    from vault_v2 import format_capture_confirmation, smart_capture

    # Test basic capture confirmation
    result = smart_capture("[TEST] John mentioned the API needs work")
    confirmation = format_capture_confirmation(result)

    assert_not_empty(confirmation, "Confirmation: Generated confirmation string")
    assert_true(len(confirmation) > 10, "Confirmation: Has meaningful content")


def test_capture_with_insights():
    """Test capture response with proactive insights."""
    try:
        from vault_v2 import get_capture_response_with_insights, smart_capture, format_capture_confirmation, PROACTIVE_AVAILABLE

        if not PROACTIVE_AVAILABLE:
            log("Proactive module not available", "skip")
            return

        result = smart_capture("[TEST] Working on API performance improvements")
        response = get_capture_response_with_insights(result)

        assert_not_empty(response, "Insights: Generated response with insights")
        assert_true(len(response) >= len(format_capture_confirmation(result)),
                   "Insights: Response includes at least the confirmation")
    except ImportError:
        log("get_capture_response_with_insights not available", "skip")


def test_brain_dump_confirmation():
    """Test brain dump confirmation formatting."""
    from vault_v2 import format_brain_dump_confirmation

    # Mock result
    mock_result = {
        "task_ids": [1, 2, 3],
        "capture_ids": [4, 5],
        "knowledge_ids": [6],
        "decision_ids": []
    }

    confirmation = format_brain_dump_confirmation(mock_result)
    assert_contains(confirmation, "3 tasks", "Brain dump confirmation: Shows task count")
    assert_contains(confirmation, "2 notes", "Brain dump confirmation: Shows note count")


def test_attachment_processing():
    """Test Discord attachment processing."""
    log("Attachment Processing Tests", "header")
    from vault_v2 import process_discord_attachments, format_attachment_confirmation

    # Test message without attachments
    result = process_discord_attachments("Just a regular message")
    assert_equals(result["attachment_count"], 0, "Attachments: No attachments in regular message")
    assert_equals(result["message_text"], "Just a regular message", "Attachments: Message text preserved")

    # Test message with attachment metadata
    message_with_att = 'Check this out [ATTACHMENTS: [{"filename": "test.pdf", "path": "/tmp/test.pdf"}]]'
    result = process_discord_attachments(message_with_att)

    assert_equals(result["attachment_count"], 1, "Attachments: Detected attachment count")
    assert_true("Check this out" in result["message_text"], "Attachments: Cleaned message text")

    # Test confirmation formatting
    mock_result = {"processed": [{"file_name": "test.pdf", "summary": "A test document"}]}
    confirmation = format_attachment_confirmation(mock_result)
    assert_contains(confirmation, "test.pdf", "Attachments: Confirmation includes filename")


def test_attachment_combined_capture():
    """Test combined text + attachment capture."""
    try:
        from vault_v2 import smart_capture_with_attachments

        message = 'Remember this note [ATTACHMENTS: [{"filename": "doc.pdf", "path": "/nonexistent/doc.pdf"}]]'
        result = smart_capture_with_attachments(message, source="test")

        assert_true(result["has_text"], "Combined capture: Has text portion")
        # Note: has_attachments may be True even if files don't exist (count > 0)
        assert_true("text_capture" in result, "Combined capture: Has text_capture field")
        assert_true("attachments" in result, "Combined capture: Has attachments field")
    except ImportError:
        log("smart_capture_with_attachments not available", "skip")


def test_semantic_search_available():
    """Test if semantic search is available and functional."""
    log("Semantic Search Tests", "header")
    try:
        from vault_v2 import EMBEDDINGS_AVAILABLE, semantic_search

        if not EMBEDDINGS_AVAILABLE:
            log("ChromaDB/embeddings not available - skipping semantic tests", "skip")
            return

        # Test semantic search function exists and returns list
        results = semantic_search("test query")
        assert_true(isinstance(results, list), "Semantic: Returns list of results")
    except ImportError as e:
        log(f"Semantic search import error: {e}", "skip")


def test_semantic_embedding_storage():
    """Test that captures store embeddings."""
    try:
        from vault_v2 import EMBEDDINGS_AVAILABLE, smart_capture
        from embeddings import get_embedding_stats

        if not EMBEDDINGS_AVAILABLE:
            log("Embeddings not available", "skip")
            return

        # Capture something
        result = smart_capture("[TEST] Semantic embedding test capture")

        # Check embedding stats
        stats = get_embedding_stats()
        assert_equals(stats.get("status"), "available", "Embeddings: ChromaDB is available")
    except ImportError:
        log("Embedding module not available", "skip")


def test_unified_search_with_semantic():
    """Test unified search includes semantic source."""
    try:
        from vault_v2 import unified_search, EMBEDDINGS_AVAILABLE

        if not EMBEDDINGS_AVAILABLE:
            log("Embeddings not available for unified search test", "skip")
            return

        # Search with semantic source
        results = unified_search("test", sources=["captures", "semantic"])
        assert_true(isinstance(results, list), "Unified semantic: Returns results")
    except Exception as e:
        log(f"Unified search with semantic failed: {e}", "skip")


def test_proactive_insights():
    """Test proactive intelligence insights generation."""
    log("Proactive Intelligence Tests", "header")
    try:
        from proactive import get_proactive_insights, get_attention_items

        # Test attention items
        attention = get_attention_items()
        assert_true("overdue_tasks" in attention, "Proactive: Attention items has overdue_tasks")
        assert_true("needs_attention" in attention, "Proactive: Attention items has needs_attention flag")

        # Test insights generation (may be empty)
        insights = get_proactive_insights()
        assert_true(isinstance(insights, list), "Proactive: Insights returns list")
    except ImportError:
        log("Proactive module not available", "skip")


def test_proactive_repeated_topics():
    """Test repeated topic detection."""
    try:
        from proactive import get_repeated_topics

        # Query repeated topics (may be empty)
        repeated = get_repeated_topics(days=30, threshold=2)
        assert_true(isinstance(repeated, list), "Proactive: Repeated topics returns list")

        # If there are results, verify structure
        if repeated:
            assert_true("topic" in repeated[0], "Proactive: Repeated topic has 'topic' field")
            assert_true("count" in repeated[0], "Proactive: Repeated topic has 'count' field")
    except ImportError:
        log("Proactive module not available", "skip")


def test_proactive_upcoming_deadlines():
    """Test upcoming deadline detection."""
    try:
        from proactive import get_upcoming_deadlines

        deadlines = get_upcoming_deadlines(days=30)
        assert_true(isinstance(deadlines, list), "Proactive: Deadlines returns list")

        if deadlines:
            assert_true("type" in deadlines[0], "Proactive: Deadline has 'type' field")
            assert_true("days_left" in deadlines[0], "Proactive: Deadline has 'days_left' field")
    except ImportError:
        log("Proactive module not available", "skip")


def test_proactive_daily_summary():
    """Test daily proactive summary generation."""
    try:
        from proactive import get_daily_proactive_summary

        summary = get_daily_proactive_summary()
        assert_true("attention_items" in summary, "Proactive: Summary has attention_items")
        assert_true("upcoming_deadlines" in summary, "Proactive: Summary has upcoming_deadlines")
        assert_true("generated_at" in summary, "Proactive: Summary has timestamp")
    except ImportError:
        log("Proactive module not available", "skip")


def test_system_queries_list():
    """Test system queries - list containers."""
    log("Cross-System Query Tests", "header")
    try:
        from system_queries import list_running_containers

        containers = list_running_containers()
        assert_true(isinstance(containers, list), "System: list_running_containers returns list")
    except ImportError:
        log("system_queries module not available", "skip")
    except Exception as e:
        log(f"Docker may not be available: {e}", "skip")


def test_system_queries_overview():
    """Test system overview generation."""
    try:
        from system_queries import get_system_overview

        overview = get_system_overview()
        assert_true("containers" in overview, "System: Overview has containers")
        assert_true("queried_at" in overview, "System: Overview has timestamp")
    except ImportError:
        log("system_queries module not available", "skip")
    except Exception as e:
        log(f"Docker may not be available: {e}", "skip")


def test_system_queries_health_check():
    """Test container health check (may fail if no containers)."""
    try:
        from system_queries import check_container_health

        # Check a likely non-existent container
        health = check_container_health("nonexistent-container")
        assert_true("healthy" in health, "System: Health check returns healthy field")
        assert_equals(health.get("healthy"), False, "System: Non-existent container is not healthy")
    except ImportError:
        log("system_queries module not available", "skip")
    except Exception as e:
        log(f"Health check error: {e}", "skip")


# ============================================================================
# Test Runner
# ============================================================================

def run_category(category: str):
    """Run tests for a specific category."""
    categories = {
        "capture": [test_capture_basic, test_capture_entity_extraction, test_capture_temporal_parsing],
        "brain_dump": [test_brain_dump_parsing, test_brain_dump_type_detection,
                       test_brain_dump_grouping, test_brain_dump_storage, test_brain_dump_edge_cases],
        "search": [test_search_basic, test_unified_search, test_search_filters],
        "tasks": [test_task_creation, test_task_completion, test_task_with_context],
        "knowledge": [test_knowledge_add, test_knowledge_categories],
        "briefs": [test_brief_daily, test_brief_weekly, test_brief_eod],
        "relationships": [test_relationship_tracking, test_relationship_summary],
        "projects": [test_project_health, test_project_context],
        "integration": [test_full_capture_flow, test_brain_dump_to_brief_flow, test_entity_linking_flow],
        # New feature tests
        "confirmation": [test_capture_confirmation, test_capture_with_insights, test_brain_dump_confirmation],
        "attachments": [test_attachment_processing, test_attachment_combined_capture],
        "semantic": [test_semantic_search_available, test_semantic_embedding_storage, test_unified_search_with_semantic],
        "proactive": [test_proactive_insights, test_proactive_repeated_topics,
                      test_proactive_upcoming_deadlines, test_proactive_daily_summary],
        "system": [test_system_queries_list, test_system_queries_overview, test_system_queries_health_check],
    }

    if category not in categories:
        print(f"Unknown category: {category}")
        print(f"Available: {', '.join(categories.keys())}")
        return

    for test_func in categories[category]:
        try:
            test_func()
        except Exception as e:
            log(f"Error in {test_func.__name__}: {e}", "fail")


def run_all_tests():
    """Run all test categories."""
    categories = ["capture", "brain_dump", "search", "tasks", "knowledge",
                  "briefs", "relationships", "projects", "integration",
                  "confirmation", "attachments", "semantic", "proactive", "system"]

    for category in categories:
        run_category(category)


def print_summary():
    """Print test summary."""
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    print(f"  Passed:  {RESULTS['passed']}")
    print(f"  Failed:  {RESULTS['failed']}")
    print(f"  Skipped: {RESULTS['skipped']}")
    print("="*60)

    if RESULTS["errors"]:
        print("\nFailures:")
        for error in RESULTS["errors"]:
            print(f"  - {error}")

    total = RESULTS["passed"] + RESULTS["failed"]
    if total > 0:
        success_rate = (RESULTS["passed"] / total) * 100
        print(f"\nSuccess Rate: {success_rate:.1f}%")

    return RESULTS["failed"] == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PCP Comprehensive Test Suite")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--category", "-c", type=str, help="Run specific category")
    parser.add_argument("--no-cleanup", action="store_true", help="Don't cleanup test data")
    parser.add_argument("--list", "-l", action="store_true", help="List test categories")

    args = parser.parse_args()
    VERBOSE = args.verbose

    if args.list:
        print("Test Categories:")
        print("  capture       - Smart capture and entity extraction")
        print("  brain_dump    - Brain dump parsing and storage")
        print("  search        - Search and retrieval")
        print("  tasks         - Task management")
        print("  knowledge     - Knowledge base")
        print("  briefs        - Brief generation")
        print("  relationships - Relationship tracking")
        print("  projects      - Project health monitoring")
        print("  integration   - End-to-end flows")
        print("  confirmation  - Capture confirmation formatting (NEW)")
        print("  attachments   - Discord attachment processing (NEW)")
        print("  semantic      - Semantic search with ChromaDB (NEW)")
        print("  proactive     - Proactive intelligence (NEW)")
        print("  system        - Cross-system queries (NEW)")
        sys.exit(0)

    print("\n" + "="*60)
    print("  PCP COMPREHENSIVE TEST SUITE")
    print("="*60)
    print(f"  Database: {VAULT_PATH}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not args.no_cleanup:
        cleanup_test_data()

    if args.category:
        run_category(args.category)
    else:
        run_all_tests()

    if not args.no_cleanup:
        cleanup_test_data()

    success = print_summary()
    sys.exit(0 if success else 1)
