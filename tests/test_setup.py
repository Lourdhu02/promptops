"""
Basic sanity tests to verify setup
"""
import pytest


def test_imports():
    """Test that core packages can be imported"""
    try:
        import fastapi
        import sqlalchemy
        import redis
        import click
        import pydantic
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import required package: {e}")


def test_python_version():
    """Ensure Python 3.11+ is being used"""
    import sys
    assert sys.version_info >= (3, 11), "Python 3.11+ required"


def test_environment():
    """Test that .env file exists"""
    from pathlib import Path
    env_file = Path(".env")
    
    if not env_file.exists():
        pytest.skip(".env file not found - this is expected for fresh setup")
    
    # If .env exists, verify it has required keys
    with open(env_file) as f:
        content = f.read()
        assert "DATABASE_URL" in content
        assert "REDIS_URL" in content


@pytest.mark.unit
def test_placeholder():
    """Placeholder test - will be replaced with real tests"""
    assert 1 + 1 == 2