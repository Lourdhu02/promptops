
"""
Initialize PostgreSQL database schema for PromptOps.
Run this after setting up your DATABASE_URL in .env
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL not found in .env file")
    print("Please create a .env file with:")
    print("DATABASE_URL=postgresql://user:root@localhost:5432/promptops")
    sys.exit(1)


def create_tables():
    """Create all database tables"""
    
    engine = create_engine(DATABASE_URL, echo=True)
    
    # Test connection
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"\n✅ Connected to PostgreSQL: {version}\n")
    except Exception as e:
        print(f"\n❌ Failed to connect to database: {e}")
        print(f"   DATABASE_URL: {DATABASE_URL}")
        sys.exit(1)
    
    # Create tables using raw SQL for now
    # (We'll replace this with SQLAlchemy models later)
    
    with engine.connect() as conn:
        # Enable UUID extension
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"))
        conn.commit()
        
        # PromptVersion table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS prompt_versions (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                content TEXT NOT NULL,
                hash VARCHAR(64) NOT NULL UNIQUE,
                parent_id UUID REFERENCES prompt_versions(id),
                author VARCHAR(255) NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tags JSONB DEFAULT '[]',
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        print("✅ Created table: prompt_versions")
        
        # EvalResult table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS eval_results (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                version_id UUID NOT NULL REFERENCES prompt_versions(id) ON DELETE CASCADE,
                score_accuracy FLOAT,
                score_hallucination FLOAT,
                score_relevance FLOAT,
                score_latency_p95 FLOAT,
                score_consistency FLOAT,
                dataset_id UUID,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        print("✅ Created table: eval_results")
        
        # Deployment table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS deployments (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                version_id UUID NOT NULL REFERENCES prompt_versions(id),
                environment VARCHAR(50) NOT NULL,
                deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deployed_by VARCHAR(255) NOT NULL,
                rollback_version_id UUID REFERENCES prompt_versions(id),
                is_active BOOLEAN DEFAULT TRUE
            );
        """))
        print("✅ Created table: deployments")
        
        # ABTest table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ab_tests (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                version_a_id UUID NOT NULL REFERENCES prompt_versions(id),
                version_b_id UUID NOT NULL REFERENCES prompt_versions(id),
                traffic_split FLOAT DEFAULT 0.5,
                start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_date TIMESTAMP,
                status VARCHAR(50) DEFAULT 'running',
                winner_id UUID REFERENCES prompt_versions(id),
                p_value FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        print("✅ Created table: ab_tests")
        
        # Dataset table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS datasets (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                name VARCHAR(255) NOT NULL,
                format VARCHAR(50) NOT NULL,
                rows INTEGER DEFAULT 0,
                file_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        print("✅ Created table: datasets")
        
        # Review table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS reviews (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                version_id UUID NOT NULL REFERENCES prompt_versions(id),
                reviewer VARCHAR(255) NOT NULL,
                status VARCHAR(50) NOT NULL,
                comments TEXT,
                reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        print("✅ Created table: reviews")
        
        # Create indexes
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_prompt_versions_hash ON prompt_versions(hash);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_prompt_versions_parent ON prompt_versions(parent_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_eval_results_version ON eval_results(version_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_deployments_version ON deployments(version_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_deployments_env ON deployments(environment);"))
        print("✅ Created indexes")
        
        conn.commit()
    
    print("\n🎉 Database initialization complete!\n")
    print("Next steps:")
    print("  1. Run: promptops init")
    print("  2. Create your first prompt YAML file")
    print("  3. Run: promptops add <file>")
    print("  4. Run: promptops commit -m 'Initial version'")


if __name__ == "__main__":
    print("=" * 60)
    print("PromptOps — Database Initialization")
    print("=" * 60)
    print()
    
    create_tables()