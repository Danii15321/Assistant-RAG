CREATE TABLE conversations (
 id uuid PRIMARY KEY,
 owner_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 title text NOT NULL DEFAULT 'Nouvelle conversation',
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 next_ordinal int NOT NULL DEFAULT 1,
 lease_token uuid,
 lease_until timestamptz,
 UNIQUE (id,owner_id)
);
CREATE INDEX conversations_owner_updated ON conversations(owner_id,updated_at DESC,id);
CREATE TABLE conversation_exchanges (
 id uuid PRIMARY KEY,
 conversation_id uuid NOT NULL,
 owner_id uuid NOT NULL,
 request_id uuid NOT NULL,
 fingerprint text NOT NULL,
 ordinal int NOT NULL CHECK (ordinal>0),
 question text NOT NULL CHECK (length(question) BETWEEN 1 AND 1000),
 document_ids jsonb,
 state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','answered','insufficient_context','failed')),
 response jsonb,
 error_code text,
 created_at timestamptz NOT NULL DEFAULT now(),
 completed_at timestamptz,
 FOREIGN KEY (conversation_id,owner_id) REFERENCES conversations(id,owner_id) ON DELETE CASCADE,
 UNIQUE (conversation_id,request_id),
 UNIQUE (conversation_id,ordinal),
 UNIQUE (id,owner_id),
 CHECK ((state IN ('answered','insufficient_context')) = (response IS NOT NULL))
);
CREATE TABLE conversation_sources (
 exchange_id uuid NOT NULL,
 owner_id uuid NOT NULL,
 source_id text NOT NULL,
 document_id uuid,
 status text NOT NULL DEFAULT 'available' CHECK (status IN ('available','deleted')),
 payload jsonb NOT NULL,
 PRIMARY KEY (exchange_id,source_id),
 FOREIGN KEY (exchange_id,owner_id) REFERENCES conversation_exchanges(id,owner_id) ON DELETE CASCADE,
 FOREIGN KEY (document_id,owner_id) REFERENCES documents(id,owner_id) ON DELETE SET NULL (document_id)
);
CREATE INDEX conversation_sources_document ON conversation_sources(document_id,owner_id);
CREATE FUNCTION scrub_conversation_sources() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 UPDATE conversation_sources SET document_id=NULL,status='deleted',payload=payload-'text'-'quotes'
 WHERE document_id=OLD.id AND owner_id=OLD.owner_id;
 RETURN OLD;
END
$$;
CREATE TRIGGER conversations_document_excluded AFTER UPDATE OF state ON documents
 FOR EACH ROW WHEN (NEW.state='deleting') EXECUTE FUNCTION scrub_conversation_sources();
CREATE TRIGGER conversations_document_deleted BEFORE DELETE ON documents
 FOR EACH ROW EXECUTE FUNCTION scrub_conversation_sources();
