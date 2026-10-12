CREATE TABLE documents (
 id uuid PRIMARY KEY,
 owner_id uuid NOT NULL REFERENCES users(id),
 filename text NOT NULL,
 extension text NOT NULL CHECK (extension IN ('pdf','docx','txt')),
 content_type text NOT NULL,
 size_bytes bigint NOT NULL CHECK (size_bytes > 0),
 actual_size bigint,
 sha256 text,
 state text NOT NULL CHECK (state IN ('uploading','queued','processing','ready','failed','deleting')),
 stage text NOT NULL DEFAULT 'upload',
 error_code text,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL,
 upload_hash text UNIQUE,
 session_id text NOT NULL,
 parser_version text,
 unit_count int NOT NULL DEFAULT 0,
 generation int NOT NULL DEFAULT 1,
 UNIQUE (id, owner_id)
);
CREATE INDEX documents_owner_created ON documents(owner_id, created_at DESC, id);
CREATE UNIQUE INDEX documents_owner_hash ON documents(owner_id, sha256) WHERE state <> 'deleting';
CREATE TABLE extracted_units (
 document_id uuid NOT NULL,
 owner_id uuid NOT NULL,
 ordinal int NOT NULL,
 kind text NOT NULL CHECK (kind IN ('page','paragraph','line')),
 number int NOT NULL CHECK (number > 0),
 text text NOT NULL,
 PRIMARY KEY (document_id, ordinal),
 FOREIGN KEY (document_id, owner_id) REFERENCES documents(id, owner_id) ON DELETE CASCADE
);
CREATE TABLE ingestion_jobs (
 id uuid PRIMARY KEY,
 document_id uuid NOT NULL,
 owner_id uuid NOT NULL,
 kind text NOT NULL CHECK (kind IN ('extract','delete')),
 generation int NOT NULL,
 status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','done')),
 attempts int NOT NULL DEFAULT 0,
 lease_until timestamptz,
 lease_token uuid,
 created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY (document_id, owner_id) REFERENCES documents(id, owner_id) ON DELETE CASCADE,
 UNIQUE (document_id, kind, generation)
);
CREATE INDEX ingestion_jobs_pending ON ingestion_jobs(status, created_at);
