"""
Neo4j service for Document_Intelligence_RAG.

Week 12 purpose:
- Connect Python/FastAPI project to Neo4j.
- Store document graph data.
- Create Document, Chunk, and Entity nodes.
- Create relationships:
    Document -[:HAS_CHUNK]-> Chunk
    Chunk -[:MENTIONS]-> Entity
    Entity -[:APPEARS_IN]-> Document

Important:
- Neo4j is NOT replacing Pinecone.
- Pinecone is for semantic/vector search.
- Neo4j is for entity relationship intelligence.
"""

# Import annotations so type hints work cleanly.
from __future__ import annotations

# Import os to read .env/environment variables.
import os

# Import typing helpers.
from typing import Any, Dict, List, Optional

# Import Neo4j official Python driver.
from neo4j import GraphDatabase

# Import Driver type for clean type hints.
from neo4j import Driver

# Try to load .env values.
# This is useful when running scripts directly from PowerShell.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # If python-dotenv is not installed, we continue.
    # Your app may already load env variables elsewhere.
    pass


# Global driver object.
# Simple meaning:
# We keep one reusable Neo4j connection manager instead of creating a new one every time.
_NEO4J_DRIVER: Optional[Driver] = None


def is_neo4j_enabled() -> bool:
    """
    Check whether Neo4j is enabled.

    Simple meaning:
    If NEO4J_ENABLED=false, worker/API can skip graph storage safely.
    """

    # Read value from environment.
    value = os.getenv("NEO4J_ENABLED", "false")

    # Convert text value to boolean.
    return value.lower() in {"true", "1", "yes"}


def get_neo4j_uri() -> str:
    """
    Read Neo4j URI from environment.

    URI means connection address.

    Example:
    neo4j+s://abc123.databases.neo4j.io
    """

    # Read URI.
    uri = os.getenv("NEO4J_URI")

    # If missing, raise clear error.
    if not uri:
        raise RuntimeError("Missing NEO4J_URI in .env")

    # Return URI.
    return uri


def get_neo4j_username() -> str:
    """
    Read Neo4j username from environment.
    """

    # Read username.
    username = os.getenv("NEO4J_USERNAME")

    # If missing, raise clear error.
    if not username:
        raise RuntimeError("Missing NEO4J_USERNAME in .env")

    # Return username.
    return username


def get_neo4j_password() -> str:
    """
    Read Neo4j password from environment.
    """

    # Read password.
    password = os.getenv("NEO4J_PASSWORD")

    # If missing, raise clear error.
    if not password:
        raise RuntimeError("Missing NEO4J_PASSWORD in .env")

    # Return password.
    return password


def get_neo4j_database() -> str:
    """
    Read Neo4j database name from environment.

    For Neo4j Aura Free, this is usually:
    neo4j
    """

    # Return database name, defaulting to neo4j.
    return os.getenv("NEO4J_DATABASE", "neo4j")


def get_neo4j_driver() -> Driver:
    """
    Create or return Neo4j driver.

    New word:
    Driver means the Python connector object that talks to Neo4j.
    """

    # Tell Python we want to use/update the global driver variable.
    global _NEO4J_DRIVER

    # If driver already exists, reuse it.
    if _NEO4J_DRIVER is not None:
        return _NEO4J_DRIVER

    # Read connection values from environment.
    uri = get_neo4j_uri()
    username = get_neo4j_username()
    password = get_neo4j_password()

    # Create Neo4j driver.
    _NEO4J_DRIVER = GraphDatabase.driver(
        uri,
        auth=(username, password),
    )

    # Return driver.
    return _NEO4J_DRIVER


def close_neo4j_driver() -> None:
    """
    Close Neo4j driver.

    Simple meaning:
    This releases network/database resources.
    """

    # Tell Python we want to update the global variable.
    global _NEO4J_DRIVER

    # If driver exists, close it.
    if _NEO4J_DRIVER is not None:
        _NEO4J_DRIVER.close()

    # Reset global driver to None.
    _NEO4J_DRIVER = None


def verify_neo4j_connection() -> bool:
    """
    Verify that Python can connect to Neo4j.

    Returns:
    True if connection works.
    """

    # Get driver.
    driver = get_neo4j_driver()

    # Ask driver to verify connection.
    driver.verify_connectivity()

    # If no exception happened, connection is OK.
    return True


def create_graph_constraints() -> None:
    """
    Create Neo4j constraints.

    New word:
    Constraint means a database rule.

    Why constraints matter:
    They prevent duplicates and make lookups faster.

    We create:
    - one Document per document_id
    - one Chunk per chunk_id
    - one Entity per entity_key
    """

    # Get driver.
    driver = get_neo4j_driver()

    # Get database name.
    database = get_neo4j_database()

    # Open Neo4j session.
    with driver.session(database=database) as session:
        # Create unique constraint for Document.document_id.
        session.run(
            """
            CREATE CONSTRAINT document_id_unique IF NOT EXISTS
            FOR (d:Document)
            REQUIRE d.document_id IS UNIQUE
            """
        )

        # Create unique constraint for Chunk.chunk_id.
        session.run(
            """
            CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS
            FOR (c:Chunk)
            REQUIRE c.chunk_id IS UNIQUE
            """
        )

        # Create unique constraint for Entity.entity_key.
        session.run(
            """
            CREATE CONSTRAINT entity_key_unique IF NOT EXISTS
            FOR (e:Entity)
            REQUIRE e.entity_key IS UNIQUE
            """
        )


def build_entity_key(normalized_text: str, label: str) -> str:
    """
    Build unique key for entity.

    Example:
    normalized_text = "andhra university"
    label = "ORG"

    entity_key = "andhra university::ORG"

    Why:
    The same text can sometimes have different labels.
    This key helps Neo4j identify one unique entity.
    """

    # Clean normalized text.
    safe_text = (normalized_text or "").strip().lower()

    # Clean label.
    safe_label = (label or "").strip().upper()

    # Return combined key.
    return f"{safe_text}::{safe_label}"


def shorten_text(text: Optional[str], max_length: int = 500) -> str:
    """
    Shorten long text for Neo4j preview.

    Important:
    Neo4j should not become the main place for full chunk text.
    We store only preview text here.

    Full redacted chunk text is already in local/S3 artifacts and Pinecone metadata.
    """

    # If text is missing, return empty string.
    if not text:
        return ""

    # Replace newlines with spaces.
    cleaned = " ".join(text.split())

    # If text is already short, return it.
    if len(cleaned) <= max_length:
        return cleaned

    # Otherwise return shortened preview.
    return cleaned[:max_length] + "..."


def upsert_document_node(document: Dict[str, Any]) -> None:
    """
    Create or update one Document node.

    Input example:
    {
        "document_id": "doc_123",
        "filename": "sample.pdf",
        "parser_used": "docling"
    }
    """

    # Get required document_id.
    document_id = document.get("document_id")

    # document_id is required.
    if not document_id:
        raise ValueError("document_id is required to create Document node")

    # Get optional fields.
    filename = document.get("filename", "")
    parser_used = document.get("parser_used", "")

    # Get driver and database.
    driver = get_neo4j_driver()
    database = get_neo4j_database()

    # Open session.
    with driver.session(database=database) as session:
        # MERGE prevents duplicate Document nodes.
        session.run(
            """
            MERGE (d:Document {document_id: $document_id})
            ON CREATE SET d.created_at = datetime()
            SET
                d.filename = $filename,
                d.parser_used = $parser_used,
                d.updated_at = datetime()
            """,
            document_id=document_id,
            filename=filename,
            parser_used=parser_used,
        )


def upsert_chunk_node(document_id: str, chunk: Dict[str, Any]) -> None:
    """
    Create or update one Chunk node and connect it to Document.

    Relationship created:
    (Document)-[:HAS_CHUNK]->(Chunk)
    """

    # Get chunk_id.
    chunk_id = chunk.get("chunk_id")

    # chunk_id is required.
    if not chunk_id:
        raise ValueError("chunk_id is required to create Chunk node")

    # Read chunk fields.
    page_number = chunk.get("page_number")
    section_title = chunk.get("section_title", "")
    content_type = chunk.get("content_type", "")
    word_count = chunk.get("word_count", 0)

    # Chunk text may be stored as text or source_text.
    text = chunk.get("text") or chunk.get("source_text") or ""

    # Store only preview in Neo4j.
    source_preview = shorten_text(text, max_length=500)

    # Get driver and database.
    driver = get_neo4j_driver()
    database = get_neo4j_database()

    # Open session.
    with driver.session(database=database) as session:
        # Create/update Chunk.
        # Then connect Document to Chunk using HAS_CHUNK.
        session.run(
            """
            MATCH (d:Document {document_id: $document_id})
            MERGE (c:Chunk {chunk_id: $chunk_id})
            ON CREATE SET c.created_at = datetime()
            SET
                c.document_id = $document_id,
                c.page_number = $page_number,
                c.section_title = $section_title,
                c.content_type = $content_type,
                c.word_count = $word_count,
                c.source_preview = $source_preview,
                c.updated_at = datetime()
            MERGE (d)-[:HAS_CHUNK]->(c)
            """,
            document_id=document_id,
            chunk_id=chunk_id,
            page_number=page_number,
            section_title=section_title,
            content_type=content_type,
            word_count=word_count,
            source_preview=source_preview,
        )


def upsert_entity_mention(document_id: str, entity: Dict[str, Any]) -> None:
    """
    Create or update Entity node and relationships.

    Relationships created:
    (Chunk)-[:MENTIONS]->(Entity)
    (Entity)-[:APPEARS_IN]->(Document)

    Input entity example:
    {
        "text": "Andhra University",
        "normalized_text": "andhra university",
        "label": "ORG",
        "chunk_id": "chunk_1",
        "page_number": 1,
        "section_title": "Education"
    }
    """

    # Get required values.
    entity_text = entity.get("text")
    normalized_text = entity.get("normalized_text")
    label = entity.get("label")
    chunk_id = entity.get("chunk_id")

    # Skip if important fields are missing.
    if not entity_text or not normalized_text or not label or not chunk_id:
        return

    # Build stable entity key.
    entity_key = build_entity_key(normalized_text, label)

    # Optional metadata.
    page_number = entity.get("page_number")
    section_title = entity.get("section_title", "")
    content_type = entity.get("content_type", "")

    # Get driver and database.
    driver = get_neo4j_driver()
    database = get_neo4j_database()

    # Open session.
    with driver.session(database=database) as session:
        # Create/update Entity.
        # Connect Chunk -> Entity.
        # Connect Entity -> Document.
        session.run(
            """
            MATCH (d:Document {document_id: $document_id})
            MATCH (c:Chunk {chunk_id: $chunk_id})
            MERGE (e:Entity {entity_key: $entity_key})
            ON CREATE SET e.created_at = datetime()
            SET
                e.name = $entity_text,
                e.normalized_text = $normalized_text,
                e.label = $label,
                e.updated_at = datetime()
            MERGE (c)-[m:MENTIONS]->(e)
            ON CREATE SET m.created_at = datetime()
            SET
                m.page_number = $page_number,
                m.section_title = $section_title,
                m.content_type = $content_type,
                m.updated_at = datetime()
            MERGE (e)-[a:APPEARS_IN]->(d)
            ON CREATE SET a.created_at = datetime()
            SET a.updated_at = datetime()
            """,
            document_id=document_id,
            chunk_id=chunk_id,
            entity_key=entity_key,
            entity_text=entity_text,
            normalized_text=normalized_text,
            label=label,
            page_number=page_number,
            section_title=section_title,
            content_type=content_type,
        )


def upsert_document_graph(
    document: Dict[str, Any],
    chunks: List[Dict[str, Any]],
    entity_mentions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Store full document graph in Neo4j.

    Steps:
    1. Create constraints.
    2. Create Document node.
    3. Create Chunk nodes.
    4. Create Entity nodes.
    5. Create relationships.

    Returns:
    Small summary dictionary.
    """

    # If Neo4j is disabled, skip safely.
    if not is_neo4j_enabled():
        return {
            "neo4j_enabled": False,
            "document_id": document.get("document_id"),
            "chunks_written": 0,
            "entity_mentions_written": 0,
        }

    # Get document_id.
    document_id = document.get("document_id")

    # document_id is required.
    if not document_id:
        raise ValueError("document_id is required")

    # Create database constraints.
    create_graph_constraints()

    # Create/update Document node.
    upsert_document_node(document)

    # Count chunks written.
    chunks_written = 0

    # Create/update each Chunk node.
    for chunk in chunks:
        upsert_chunk_node(document_id=document_id, chunk=chunk)
        chunks_written += 1

    # Count entity mentions written.
    entity_mentions_written = 0

    # Create/update each Entity mention.
    for entity in entity_mentions:
        upsert_entity_mention(document_id=document_id, entity=entity)
        entity_mentions_written += 1

    # Return useful summary.
    return {
        "neo4j_enabled": True,
        "document_id": document_id,
        "chunks_written": chunks_written,
        "entity_mentions_written": entity_mentions_written,
    }


def get_entities_for_document(document_id: str) -> List[Dict[str, Any]]:
    """
    Fetch summarized entities for one document.

    This will be used later by:
    GET /documents/{document_id}/entities
    """

    # If document_id is missing, fail clearly.
    if not document_id:
        raise ValueError("document_id is required")

    # Get driver and database.
    driver = get_neo4j_driver()
    database = get_neo4j_database()

    # Open session.
    with driver.session(database=database) as session:
        # Query entities connected to this document.
        result = session.run(
            """
            MATCH (d:Document {document_id: $document_id})
            MATCH (d)-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e:Entity)
            WITH
                e,
                collect(DISTINCT c.page_number) AS pages,
                collect(DISTINCT c.chunk_id) AS chunk_ids,
                collect(DISTINCT c.section_title) AS sections,
                count(*) AS mention_count
            RETURN
                e.name AS name,
                e.normalized_text AS normalized_text,
                e.label AS label,
                mention_count,
                pages,
                chunk_ids,
                sections
            ORDER BY mention_count DESC, name ASC
            """,
            document_id=document_id,
        )

        # Convert Neo4j records into Python dictionaries.
        entities = []

        # Loop through result records.
        for record in result:
            entities.append(
                {
                    "name": record["name"],
                    "normalized_text": record["normalized_text"],
                    "label": record["label"],
                    "mention_count": record["mention_count"],
                    "pages": record["pages"],
                    "chunk_ids": record["chunk_ids"],
                    "sections": record["sections"],
                }
            )

        # Return final list.
        return entities


def delete_document_graph(document_id: str) -> None:
    """
    Delete graph data for one document.

    Useful for smoke tests and reprocessing.

    This deletes:
    - Document node
    - Chunk nodes belonging only to this document
    - Relationships connected to them

    Note:
    This does not delete shared Entity nodes automatically.
    Later we can add cleanup for orphan entities if needed.
    """

    # If document_id missing, fail clearly.
    if not document_id:
        raise ValueError("document_id is required")

    # Get driver and database.
    driver = get_neo4j_driver()
    database = get_neo4j_database()

    # Open session.
    with driver.session(database=database) as session:
        # Delete document and its chunks.
        session.run(
            """
            MATCH (d:Document {document_id: $document_id})
            OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
            DETACH DELETE d, c
            """,
            document_id=document_id,
        )

        # Delete orphan entities that are not mentioned by any chunk.
        session.run(
            """
            MATCH (e:Entity)
            WHERE NOT ( (:Chunk)-[:MENTIONS]->(e) )
            DETACH DELETE e
            """
        )