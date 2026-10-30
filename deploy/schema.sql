CREATE TABLE IF NOT EXISTS fds_transactions (
  id CHAR(36) PRIMARY KEY,
  created_at VARCHAR(40) NOT NULL,
  request_json JSON NOT NULL,
  decision VARCHAR(16) NOT NULL,
  risk_score DOUBLE NOT NULL,
  threshold_value DOUBLE NOT NULL,
  model_type VARCHAR(64) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fds_audit_outbox (
  event_id CHAR(36) PRIMARY KEY,
  transaction_id CHAR(36) NOT NULL,
  created_at VARCHAR(40) NOT NULL,
  event_type VARCHAR(40) NOT NULL,
  payload_json JSON NOT NULL,
  delivered_at DATETIME(6) NULL,
  attempts INT UNSIGNED NOT NULL DEFAULT 0,
  last_attempt_at DATETIME(6) NULL,
  INDEX pending_events (delivered_at, last_attempt_at, created_at),
  CONSTRAINT fk_fds_audit_transaction FOREIGN KEY (transaction_id) REFERENCES fds_transactions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
