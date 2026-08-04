-- Initial schema. Apply with:
--   docker compose exec postgres psql -U job_agent -d job_agent -f /migrations/001_init.sql

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE offer (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source            text NOT NULL,
    external_id       text NOT NULL,
    identity_key      text NOT NULL,
    url               text NOT NULL,
    payload           jsonb NOT NULL,
    embedding         vector(768),
    first_seen_at     timestamptz NOT NULL DEFAULT now(),
    last_seen_at      timestamptz NOT NULL DEFAULT now(),
    times_seen        int NOT NULL DEFAULT 1,
    UNIQUE (source, external_id)
);
CREATE INDEX ON offer (identity_key);
CREATE INDEX ON offer USING hnsw (embedding vector_cosine_ops);

CREATE TABLE offer_score (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    offer_id          uuid NOT NULL REFERENCES offer(id) ON DELETE CASCADE,
    rejection_stage   text,
    rejection_reason  text,
    rule_score        numeric(4,3),
    similarity_score  numeric(4,3),
    knn_score         numeric(4,3),
    llm_score         numeric(4,3),
    final_score       numeric(4,3),
    rationale         text,
    features          jsonb NOT NULL DEFAULT '{}',
    scoring_version   text NOT NULL,
    cost_usd          numeric(10,6) DEFAULT 0,
    created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON offer_score (offer_id);

CREATE TABLE my_rating (
    id                        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    offer_id                  uuid NOT NULL UNIQUE REFERENCES offer(id) ON DELETE CASCADE,
    rating                    text NOT NULL,
    reason                    text,
    features_at_rating_time   jsonb NOT NULL,
    system_score              numeric(4,3),
    created_at                timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE notification (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    offer_id        uuid NOT NULL REFERENCES offer(id) ON DELETE CASCADE,
    channel         text NOT NULL DEFAULT 'discord',
    message_id      text,
    is_exploration  boolean NOT NULL DEFAULT false,
    sent_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (offer_id, channel)
);

CREATE TABLE preference_profile (
    version           int PRIMARY KEY,
    centroid_positive vector(768),
    centroid_negative vector(768),
    count_positive    int NOT NULL,
    count_negative    int NOT NULL,
    thresholds        jsonb NOT NULL,
    feature_weights   jsonb NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now()
);
