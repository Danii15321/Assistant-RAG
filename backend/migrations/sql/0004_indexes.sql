ALTER TABLE documents ADD COLUMN chunk_count integer NOT NULL DEFAULT 0 CHECK (chunk_count>=0);
ALTER TABLE documents ADD COLUMN embedded_count integer NOT NULL DEFAULT 0 CHECK (embedded_count>=0 AND embedded_count<=chunk_count);
ALTER TABLE documents ADD COLUMN index_version text;
ALTER TABLE ingestion_jobs DROP CONSTRAINT ingestion_jobs_kind_check;
ALTER TABLE ingestion_jobs ADD CONSTRAINT ingestion_jobs_kind_check CHECK (kind IN ('extract','index','delete'));
CREATE TABLE index_runs (
 document_id uuid NOT NULL, owner_id uuid NOT NULL, generation integer NOT NULL,
 index_version text NOT NULL, expected_count integer NOT NULL CHECK (expected_count BETWEEN 1 AND 20000),
 manifest_sha256 text NOT NULL CHECK (length(manifest_sha256)=64),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(document_id,generation), UNIQUE(document_id,owner_id,generation),
 FOREIGN KEY(document_id,owner_id) REFERENCES documents(id,owner_id) ON DELETE CASCADE
);
CREATE INDEX index_runs_owner ON index_runs(owner_id);
CREATE TABLE index_chunks (
 document_id uuid NOT NULL, owner_id uuid NOT NULL, generation integer NOT NULL,
 ordinal integer NOT NULL CHECK (ordinal>0), text text NOT NULL,
 token_count integer NOT NULL CHECK (token_count BETWEEN 1 AND 300),
 start_offset integer NOT NULL CHECK (start_offset>=0), end_offset integer NOT NULL CHECK (end_offset>start_offset),
 kind text NOT NULL CHECK (kind IN ('page','paragraph','line')),
 start_number integer NOT NULL CHECK (start_number>0), end_number integer NOT NULL CHECK (end_number>=start_number),
 start_unit integer NOT NULL CHECK (start_unit>0), end_unit integer NOT NULL CHECK (end_unit>=start_unit),
 embedding vector(384),
 PRIMARY KEY(document_id,generation,ordinal),
 FOREIGN KEY(document_id,owner_id,generation) REFERENCES index_runs(document_id,owner_id,generation) ON DELETE CASCADE
);
CREATE INDEX index_chunks_owner ON index_chunks(owner_id,document_id,generation);
INSERT INTO ingestion_jobs (id,document_id,owner_id,kind,generation)
 SELECT gen_random_uuid(),id,owner_id,'index',generation FROM documents
 WHERE state='processing' AND stage='extracted' ON CONFLICT DO NOTHING;
