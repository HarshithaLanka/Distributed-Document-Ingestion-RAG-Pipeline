"""
Neo4j smoke test for Document_Intelligence_RAG.

Purpose:
This script checks whether our Python project can connect to Neo4j.

Run:
    python scripts/neo4j_smoke_test.py

Expected output:
    neo4j connection OK
    Test message from Neo4j: Neo4j is working
"""

# Import os so we can read values from environment variables.
import os

# Import sys so we can exit the script cleanly if something fails.
import sys

# Try to load .env file values into environment variables.
# This works if python-dotenv is already installed in your project.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # If python-dotenv is not installed, we do not crash here.
    # In that case, environment variables must already be set in the terminal.
    pass

# Import GraphDatabase from the official Neo4j Python driver.
from neo4j import GraphDatabase


def get_required_env(name: str) -> str:
    """
    Read a required environment variable.

    Simple meaning:
    If NEO4J_URI or password is missing, we stop early with a clear message.
    """

    # Read the environment variable value.
    value = os.getenv(name)

    # If the value is missing or empty, stop the script.
    if not value:
        print(f"Missing required environment variable: {name}")
        sys.exit(1)

    # Return the environment variable value.
    return value


def main() -> None:
    """
    Main function for checking Neo4j connectivity.
    """

    # Read Neo4j connection details from .env.
    neo4j_uri = get_required_env("NEO4J_URI")
    neo4j_username = get_required_env("NEO4J_USERNAME")
    neo4j_password = get_required_env("NEO4J_PASSWORD")
    neo4j_database = os.getenv("NEO4J_DATABASE", "neo4j")

    # Create a Neo4j driver.
    # Simple meaning:
    # The driver is the Python object that knows how to talk to Neo4j.
    driver = GraphDatabase.driver(
        neo4j_uri,
        auth=(neo4j_username, neo4j_password),
    )

    try:
        # verify_connectivity checks whether the credentials and URI are correct.
        # Neo4j docs recommend this when you want to confirm connection immediately.
        driver.verify_connectivity()

        print("neo4j connection OK")

        # Open a session to run one small Cypher query.
        # Simple meaning:
        # A session is like a temporary conversation with the database.
        with driver.session(database=neo4j_database) as session:
            # Run a tiny test query.
            result = session.run(
                'RETURN "Neo4j is working" AS message'
            )

            # Read the first row returned by Neo4j.
            record = result.single()

            # Print the message returned by Neo4j.
            print("Test message from Neo4j:", record["message"])

    finally:
        # Always close the driver after using it.
        # Simple meaning:
        # This releases network/database resources.
        driver.close()


if __name__ == "__main__":
    main()