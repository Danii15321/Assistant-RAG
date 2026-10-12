CREATE TABLE search_jobs (
 id uuid PRIMARY KEY,
 owner_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 session_id text NOT NULL REFERENCES auth_session(id) ON DELETE CASCADE,
 question text NOT NULL CHECK (length(question) BETWEEN 0 AND 2200),
 status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','done','failed')),
 embedding vector(384),
 error_code text,
 lease_token uuid,
 lease_until timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL DEFAULT now()+interval '130 seconds',
 CHECK (status IN ('done','failed') OR length(question)>0)
);
CREATE INDEX search_jobs_owner ON search_jobs(owner_id);
CREATE INDEX search_jobs_expiry ON search_jobs(expires_at);
