-- SQLite schema for the Freelancer Finder SQL agent.
-- Apply this file through freelancer_finder.data.database.initialize_database().

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS freelancers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    email TEXT NOT NULL UNIQUE,
    age INTEGER CHECK (age IS NULL OR age BETWEEN 18 AND 120),
    bio TEXT NOT NULL DEFAULT '',
    portfolio TEXT,
    photo TEXT,
    interests_json TEXT NOT NULL DEFAULT '[]',
    languages_json TEXT NOT NULL DEFAULT '[]',
    skills_json TEXT NOT NULL DEFAULT '[]',
    work_field TEXT NOT NULL DEFAULT '',
    experience_years INTEGER CHECK (experience_years IS NULL OR experience_years >= 0),
    location TEXT,
    timezone TEXT,
    hourly_rate REAL CHECK (hourly_rate IS NULL OR hourly_rate >= 0),
    currency TEXT,
    availability_status TEXT NOT NULL DEFAULT 'unavailable'
        CHECK (availability_status IN ('available', 'partial', 'unavailable')),
    available_from TEXT,
    weekly_capacity_hours INTEGER
        CHECK (weekly_capacity_hours IS NULL OR weekly_capacity_hours BETWEEN 0 AND 168),
    is_verified INTEGER NOT NULL DEFAULT 0 CHECK (is_verified IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (hourly_rate IS NULL OR currency IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    freelancer_id TEXT NOT NULL,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    detail TEXT NOT NULL CHECK (length(trim(detail)) > 0),
    photos_json TEXT NOT NULL DEFAULT '[]',
    project_url TEXT,
    work_field TEXT NOT NULL DEFAULT '',
    skills_used_json TEXT NOT NULL DEFAULT '[]',
    role TEXT,
    client_industry TEXT,
    completed_at TEXT,
    is_public INTEGER NOT NULL DEFAULT 1 CHECK (is_public IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (freelancer_id) REFERENCES freelancers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS freelancer_embeddings (
    id TEXT PRIMARY KEY,
    freelancer_id TEXT NOT NULL,
    contents TEXT NOT NULL,
    embedding_json TEXT NOT NULL,
    project_contents TEXT,
    project_embedding_json TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    embedding_model TEXT NOT NULL,
    dimensions INTEGER NOT NULL CHECK (dimensions > 0),
    created_at TEXT NOT NULL,
    FOREIGN KEY (freelancer_id) REFERENCES freelancers(id) ON DELETE CASCADE
);

-- Local conversation memory. The random conversation ID lives in the browser;
-- no account or personal identifier is required for this demo.
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL CHECK (length(trim(content)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- Structured requirements survive beyond the bounded message window supplied
-- to the LLM. One active value is kept per supported hard-constraint field.
CREATE TABLE IF NOT EXISTS conversation_constraints (
    conversation_id TEXT NOT NULL,
    field TEXT NOT NULL CHECK (field IN (
        'availability_status', 'work_field', 'min_hourly_rate',
        'max_hourly_rate', 'currency', 'location', 'required_skills'
    )),
    value_json TEXT NOT NULL,
    source_quote TEXT NOT NULL CHECK (length(trim(source_quote)) > 0),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (conversation_id, field),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_freelancers_availability
    ON freelancers (availability_status, work_field);
CREATE INDEX IF NOT EXISTS idx_projects_freelancer_id ON projects (freelancer_id);
CREATE INDEX IF NOT EXISTS idx_freelancer_embeddings_freelancer_id
    ON freelancer_embeddings (freelancer_id);
CREATE INDEX IF NOT EXISTS idx_conversation_messages_thread
    ON conversation_messages (conversation_id, id);
CREATE INDEX IF NOT EXISTS idx_conversation_constraints_thread
    ON conversation_constraints (conversation_id, field);

CREATE TRIGGER IF NOT EXISTS set_freelancer_updated_at
AFTER UPDATE ON freelancers
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE freelancers
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;
