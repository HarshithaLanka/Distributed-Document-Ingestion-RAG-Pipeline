I am building a Production-Grade Document Intelligence and RAG Pipeline project in Python/FastAPI. Please continue from where we stopped in Week 12 and guide me step-by-step in beginner-friendly English. Whenever you give code, give full files with comments and explain the meaning of new concepts.

Project name:
Document_Intelligence_RAG

Environment:
- Windows
- VS Code
- PowerShell
- Python venv
- FastAPI backend
- Swagger testing
- AWS S3, DynamoDB, SQS
- Pinecone vector DB
- Ollama local LLM
- Embeddings: sentence-transformers/all-MiniLM-L6-v2
- Embedding dimension: 384
- Pinecone index: document-rag-index-384
- Ollama model: qwen2.5:7b-instruct
- Current parser: Docling primary, PyMuPDF fallback
- Scanned PDF/OCR paused for now
- Week 11 PII redaction completed
- Week 12 Neo4j graph work is almost completed

Important response preference:
Explain concepts first in simple English. Then give full files with comments. Explain new words like entity, graph, node, relationship, Cypher, indexing, embedding, redaction, etc.

Completed till Week 11:
Week 1:
- FastAPI app created.
- /health endpoint added.
- PDF upload endpoint added.
- Uploaded PDFs saved locally under uploads/{document_id}/.
- Metadata created.
- Document list and get-by-ID endpoints added.

Week 2:
- PDF text extraction using PyMuPDF.
- extracted_text.json created.
- Page numbers preserved.

Week 3:
- Page-aware chunking added.
- chunks.json created.
- Chunk fields include chunk_id, document_id, page_number, text, word_count.
- chunk_size=150, overlap=30.

Week 4:
- Local embeddings added using sentence-transformers/all-MiniLM-L6-v2.
- Pinecone connected.
- Pinecone index dimension 384.
- Vector upsert/indexing and vector search added.

Week 5:
- RAG Q&A with Ollama added.
- Flow: question → embedding → Pinecone search → context → Ollama → answer with citations.
- Lexical fallback added.
- Citations using chunk_id and page_number.

Week 6:
- Pytest tests added for health, upload, chunking, search, QA.
- Logging and exceptions cleaned.

Week 7:
- AWS S3 integrated.
- Original PDFs and artifacts uploaded to S3.
- S3 helper functions added.

Week 8:
- AWS SQS integrated.
- Upload sends document_id message to SQS.
- workers/document_worker.py added.
- Worker reads SQS messages and processes documents.
- Invalid old/test SQS messages without document_id deleted safely.
- Valid SQS messages deleted only after successful processing.

Week 9:
- Document state machine and events added.
- Status flow:
  queued → processing → extracting → extracted → chunking → chunked → indexing → indexed → completed.
- DynamoDB/local metadata updates added.
- Events table added.
- Status and events endpoints added.

Week 10:
- Docling layout-aware parsing added.
- PyMuPDF fallback kept.
- app/services/parser_service.py added.
- app/services/docling_parser_service.py added.
- Docling OCR disabled because scanned PDFs paused.
- Windows HuggingFace symlink issue handled using:
  HF_HUB_DISABLE_SYMLINKS=1
  HF_HUB_DISABLE_SYMLINKS_WARNING=1
- chunks.json now supports:
  section_title
  content_type
  parser_used
- Pinecone metadata stores:
  section_title
  content_type
  parser_used
- Worker uses parse_document(...) instead of direct PyMuPDF call.

Week 11:
Goal:
PII redaction and privacy-aware retrieval.

PII types handled:
- email
- phone number
- SSN-like values

Placeholders:
- email → [EMAIL_REDACTED]
- phone → [PHONE_REDACTED]
- SSN → [SSN_REDACTED]

Created:
app/services/pii_redaction_service.py

Updated:
app/constants/document_status.py
Added:
- REDACTING = "redacting"
- REDACTED = "redacted"
- PII_REDACTION_STARTED
- PII_REDACTION_COMPLETED
- redacting progress = 75
- redacted progress = 80

Updated:
app/services/s3_service.py
Added:
upload_redacted_chunks_to_s3(...)

Updated:
workers/document_worker.py
Week 11 worker flow:
queued
→ processing
→ extracting
→ extracted
→ chunking
→ chunked
→ redacting
→ redacted
→ indexing
→ indexed
→ completed

Important:
Worker sends redacted_chunks.json to Pinecone, not chunks.json.

Updated:
app/services/qa_service.py
Privacy-safe fixes:
- imports redact_text
- prefers redacted_chunks.json over chunks.json
- redacts local fallback chunks in memory
- redacts Pinecone matches
- redacts context before sending to Ollama
- redacts final answer before API response
- redacts citation source_preview
- prompt tells Ollama to keep placeholders like [EMAIL_REDACTED]

Week 11 privacy layers:
1. Before Pinecone: worker creates redacted_chunks.json.
2. Pinecone receives redacted chunks.
3. QA redacts Pinecone matches again.
4. QA local fallback prefers redacted_chunks.json.
5. Context sent to Ollama is redacted.
6. Final answer is redacted.
7. Citation previews are redacted.

Week 11 expected QA:
Question:
What is the email of professor?
Expected:
[EMAIL_REDACTED]

Week 12 work completed/almost completed:
Goal:
Entity Extraction and Neo4j Graph Storage. Roadmap says Week 12 should extract entities from chunks, create Neo4j Document/Chunk/Entity nodes, create relationships HAS_CHUNK, MENTIONS, APPEARS_IN, add GET /documents/{id}/entities, and store graph updates inside worker.

Neo4j setup:
- Neo4j Aura/local setup guided.
- .env updated with:
  NEO4J_ENABLED=true
  NEO4J_URI=neo4j+s://...
  NEO4J_USERNAME=neo4j
  NEO4J_PASSWORD=...
  NEO4J_DATABASE=neo4j
- Installed:
  pip install neo4j
- Neo4j smoke test worked.

spaCy/entity extraction:
- Installed spaCy:
  python -m pip install spacy
  python -m spacy download en_core_web_sm
- Created:
  app/services/entity_extraction_service.py
- It extracts entities from redacted chunks.
- It ignores placeholders like:
  [EMAIL_REDACTED]
  [PHONE_REDACTED]
  [SSN_REDACTED]
- It supports labels like:
  PERSON, ORG, GPE, LOC, DATE, TIME, PRODUCT, EVENT, LAW, FAC, WORK_OF_ART, NORP
- Created:
  scripts/entity_extraction_smoke_test.py
- Created tests:
  tests/test_entity_extraction_service.py
- Entity extraction test worked.

Neo4j service:
- Created:
  app/services/neo4j_service.py
- It connects to Neo4j.
- It creates constraints:
  Document.document_id unique
  Chunk.chunk_id unique
  Entity.entity_key unique
- It creates nodes:
  (:Document)
  (:Chunk)
  (:Entity)
- It creates relationships:
  (Document)-[:HAS_CHUNK]->(Chunk)
  (Chunk)-[:MENTIONS]->(Entity)
  (Entity)-[:APPEARS_IN]->(Document)
- It has functions:
  is_neo4j_enabled
  verify_neo4j_connection
  create_graph_constraints
  upsert_document_graph
  get_entities_for_document
  delete_document_graph
- Created:
  scripts/neo4j_graph_smoke_test.py
- Neo4j graph smoke test worked.

Entity API:
- Created:
  app/models/entity_models.py
- Created:
  app/routes/entity_routes.py
- Added router to app/main.py:
  from app.routes.entity_routes import router as entity_router
  app.include_router(entity_router)
- New Swagger endpoint:
  GET /documents/{document_id}/entities
- Initially got 503:
  Neo4j is disabled
- Fixed by setting NEO4J_ENABLED=true and restarting FastAPI.
- Endpoint now works.

Graph pipeline:
- Created:
  app/services/graph_pipeline_service.py
- Purpose:
  redacted_chunks.json → extract entities → write graph to Neo4j
- Created:
  scripts/graph_pipeline_smoke_test.py
- Ran for existing document:
  python scripts/graph_pipeline_smoke_test.py doc_b38fd6c9
- Then Swagger:
  GET /documents/doc_b38fd6c9/entities
  worked and showed entities.

Worker integration:
- Updated workers/document_worker.py to include Week 12 graph pipeline after PII redaction and before Pinecone indexing.
- Added import:
  from app.services.graph_pipeline_service import build_graph_for_document_from_redacted_chunks
- Added helper:
  get_document_filename(document)
- New worker flow:
  queued
  → processing
  → extracting
  → extracted
  → chunking
  → chunked
  → redacting
  → redacted
  → graph pipeline
  → indexing
  → indexed
  → completed

Important design:
- Graph pipeline uses redacted_chunks.json, not raw chunks.json.
- Neo4j stores safe redacted content previews and entity relationships.
- Graph failure does not fail the whole document processing. Pinecone indexing continues even if Neo4j has an issue.
- Worker stores metadata:
  graph_processed
  graph_written
  graph_unique_entities_count
  graph_entity_mentions_count
  graph_error_message

Current important files:
- app/main.py
- app/config.py
- app/constants/document_status.py
- app/services/entity_extraction_service.py
- app/services/neo4j_service.py
- app/services/graph_pipeline_service.py
- app/models/entity_models.py
- app/routes/entity_routes.py
- scripts/entity_extraction_smoke_test.py
- scripts/neo4j_smoke_test.py
- scripts/neo4j_graph_smoke_test.py
- scripts/graph_pipeline_smoke_test.py
- workers/document_worker.py
- tests/test_entity_extraction_service.py
- tests/test_entity_routes.py

Need to verify now:
1. Run worker import:
   python -c "from workers.document_worker import process_document; print('worker import OK')"

2. Start FastAPI:
   uvicorn app.main:app --reload

3. Start worker:
   python workers/document_worker.py

4. Upload a fresh PDF in Swagger:
   POST /documents/upload

5. Check status:
   GET /documents/{new_document_id}/status
   It should reach completed.

6. Check entities:
   GET /documents/{new_document_id}/entities
   It should show entity_count > 0 if the PDF has detectable entities.

7. Check Neo4j browser:
   MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e:Entity)
   RETURN d, c, e
   LIMIT 50;

If fresh upload works, Week 12 is fully complete.

Then commit:
git add .
git commit -m "Complete Week 12 entity extraction and Neo4j graph storage"

Next week after this:
Week 13: BM25 Keyword Search and Hybrid Retrieval.
Goal:
Improve retrieval by combining vector semantic search with exact keyword/BM25 search.



## Week 13 - BM25 Keyword Search and Hybrid Retrieval

What I learned:
- BM25 keyword search
- Tokenization
- Lexical retrieval
- Vector search vs keyword search
- Hybrid retrieval
- Score normalization
- Deduplication using chunk_id

What I built:
- Created bm25_service.py
- Added POST /search/keyword
- Created hybrid_retrieval_service.py
- Added POST /search/hybrid
- Added score normalization
- Added vector + keyword result merging
- Added duplicate chunk removal
- Added privacy-safe redaction in hybrid output

Files created/changed:
- app/services/bm25_service.py
- app/services/hybrid_retrieval_service.py
- app/models/search_models.py
- app/routes/search_routes.py
- tests/test_bm25_service.py
- tests/test_hybrid_retrieval_service.py
- requirements.txt

How I tested:
- pytest tests/test_bm25_service.py -v
- pytest tests/test_hybrid_retrieval_service.py -v
- pytest tests/test_bm25_service.py tests/test_hybrid_retrieval_service.py -v
- Swagger tested /search/vector, /search/keyword, and /search/hybrid

Status:
Week 13 completed.