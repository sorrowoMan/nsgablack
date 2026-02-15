-- NSGABlack event logging schema (MySQL 8+)
-- Scope: runs / snapshots / context_events

CREATE TABLE IF NOT EXISTS runs (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id VARCHAR(128) NOT NULL,
  entry TEXT NULL,
  status VARCHAR(32) NULL,
  seed BIGINT NULL,
  schema_version VARCHAR(32) NOT NULL DEFAULT 'v1',
  config_json JSON NULL,
  tags_json JSON NULL,
  started_at DATETIME NULL,
  finished_at DATETIME NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_runs_run_id (run_id)
);

CREATE TABLE IF NOT EXISTS snapshots (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id VARCHAR(128) NOT NULL,
  step INT NOT NULL,
  generation INT NULL,
  schema_version VARCHAR(32) NOT NULL DEFAULT 'v1',
  context_hash VARCHAR(128) NULL,
  context_json JSON NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_snapshots_run_step (run_id, step),
  KEY idx_snapshots_run_generation (run_id, generation),
  CONSTRAINT fk_snapshots_runs
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
    ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS context_events (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id VARCHAR(128) NOT NULL,
  event_id BIGINT NOT NULL,
  step INT NULL,
  generation INT NULL,
  kind VARCHAR(32) NOT NULL,
  ctx_key VARCHAR(255) NULL,
  source VARCHAR(128) NULL,
  value_json JSON NULL,
  event_time DATETIME NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_events_run_event (run_id, event_id),
  KEY idx_events_run_step (run_id, step),
  KEY idx_events_run_key (run_id, ctx_key),
  KEY idx_events_run_source (run_id, source),
  CONSTRAINT fk_events_runs
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
    ON DELETE CASCADE
);

