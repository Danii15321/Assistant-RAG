CREATE TABLE generation_attempts (
 id uuid PRIMARY KEY,
 owner_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 created_at timestamptz NOT NULL DEFAULT now(),
 reserved_tokens integer NOT NULL CHECK (reserved_tokens BETWEEN 1 AND 3100),
 prompt_tokens integer,
 completion_tokens integer,
 outcome text NOT NULL DEFAULT 'pending' CHECK (outcome IN ('pending','answered','insufficient_context','failed','revoked'))
);
CREATE INDEX generation_attempts_owner_date ON generation_attempts(owner_id,created_at);
CREATE INDEX generation_attempts_date ON generation_attempts(created_at);
CREATE TABLE generation_limits (
 singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
 lease_token uuid,
 lease_until timestamptz,
 blocked_until timestamptz
);
INSERT INTO generation_limits(singleton) VALUES (true);
