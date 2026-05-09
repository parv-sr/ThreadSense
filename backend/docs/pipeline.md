## Async ingestion pipeline

ThreadSense uses a single supported asynchronous flow:

1. `ingest_raw_file_task` creates `raw_message_chunks` rows using the Rust parser.
2. `preprocess_rawfile_task` extracts strict listing fields and writes `property_listings` plus `listing_chunks`.
3. `embed_property_listing_task` embeds `listing_chunks.content` and stores the 1536-dimensional vector in PostgreSQL via pgvector.

PostgreSQL is the source of truth for raw text, structured inventory, and embeddings.
