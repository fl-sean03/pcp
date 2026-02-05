"""
Pytest configuration and fixtures for PCP tests.
"""
import os
import sys
import pytest
import tempfile
import shutil

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

@pytest.fixture
def test_db():
    """Create a temporary test database."""
    # Create temp directory
    temp_dir = tempfile.mkdtemp(prefix='pcp_test_')
    temp_db = os.path.join(temp_dir, 'test_vault.db')

    # Set environment to use test DB
    original_db = os.environ.get('PCP_VAULT_DB')
    os.environ['PCP_VAULT_DB'] = temp_db

    # Initialize schema
    try:
        from schema_v2 import init_database
        init_database(temp_db)
    except ImportError:
        # Fallback if schema_v2 not available
        pass

    yield temp_db

    # Cleanup
    if original_db:
        os.environ['PCP_VAULT_DB'] = original_db
    else:
        os.environ.pop('PCP_VAULT_DB', None)

    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def sample_captures():
    """Sample capture data for testing."""
    return [
        {"content": "John mentioned the API needs rate limiting", "type": "note"},
        {"content": "Fix the login bug by Friday", "type": "task"},
        {"content": "Maybe we should use Redis for caching", "type": "idea"},
    ]

@pytest.fixture
def sample_brain_dump():
    """Sample brain dump text."""
    return """
    Things on my mind:
    - buy groceries: milk, eggs, bread
    - email Makayla about the visit request
    - check on MatterStack build
    - remember: Sarah prefers morning meetings
    """
