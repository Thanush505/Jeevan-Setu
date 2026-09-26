-- Migration: 004_auth_tokens.sql
-- Description: Password reset tokens and JWT blacklist tables

SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    reset_id        INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL,
    token_hash      VARCHAR(255) UNIQUE NOT NULL,
    expires_at      DATETIME NOT NULL,
    is_used         BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS token_blacklist (
    blacklist_id    INT AUTO_INCREMENT PRIMARY KEY,
    token_jti       VARCHAR(255) UNIQUE NOT NULL,
    token_type      VARCHAR(50) DEFAULT 'access',
    user_id         INT NULL,
    expires_at      DATETIME NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_reset_token ON password_reset_tokens(token_hash);
CREATE INDEX idx_reset_user ON password_reset_tokens(user_id);
CREATE INDEX idx_blacklist_jti ON token_blacklist(token_jti);

SET FOREIGN_KEY_CHECKS = 1;
