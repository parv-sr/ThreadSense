## Async ingestion pipeline

ThreadSense uses a single supported asynchronous flow:

1. `ingest_raw_file_task` creates `raw_message_chunks` rows.
2. `preprocess_rawfile_task` extracts structured listing fields and writes:
   - `property_listings`
   - `listing_chunks`
3. `embed_property_listing_task` embeds `listing_chunks.content` and upserts into Qdrant.

### Notes

- Qdrant collection name: `threadsense_listings`
- Qdrant vector name: `dense`
- `backend/src/tasks/extraction.py` remains as a legacy/backfill task path and is not part of the primary enqueue chain.
