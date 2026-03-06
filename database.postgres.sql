-- ============================================================
--  CHIT-CHAT  –  PostgreSQL schema  (Replit deployment)
--  Local machine uses MySQL (app.py / database.sql).
--  This file is ONLY for Replit. Do NOT run this locally.
-- ============================================================

-- users
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(50)  NOT NULL,
    phone_number VARCHAR(20) NOT NULL UNIQUE,
    email       VARCHAR(100) NOT NULL UNIQUE,
    password    VARCHAR(255) NOT NULL,
    profile_pic VARCHAR(255) DEFAULT NULL,
    bio         TEXT         DEFAULT NULL,
    verified    SMALLINT     DEFAULT 0,
    created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_username ON users(username);

-- messages
CREATE TABLE IF NOT EXISTS messages (
    id                   SERIAL PRIMARY KEY,
    sender_id            INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    receiver_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message              TEXT    NOT NULL,
    type                 VARCHAR(10) DEFAULT 'text'
                             CHECK (type IN ('text','voice','image','video','call','ai')),
    is_seen              SMALLINT DEFAULT 0,
    deleted_for_everyone SMALLINT DEFAULT 0,
    reply_to_id          INTEGER  DEFAULT NULL,
    reply_preview        TEXT     DEFAULT NULL,
    timestamp            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sender    ON messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_receiver  ON messages(receiver_id);
CREATE INDEX IF NOT EXISTS idx_timestamp ON messages(timestamp);

-- message_deletions
CREATE TABLE IF NOT EXISTS message_deletions (
    id         SERIAL PRIMARY KEY,
    message_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (message_id, user_id)
);

-- message_reactions
CREATE TABLE IF NOT EXISTS message_reactions (
    id         SERIAL PRIMARY KEY,
    message_id INTEGER     NOT NULL,
    user_id    INTEGER     NOT NULL,
    emoji      VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (message_id, user_id, emoji)
);

-- notifications
CREATE TABLE IF NOT EXISTS notifications (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER     NOT NULL,
    type         VARCHAR(20) NOT NULL,
    from_user_id INTEGER     DEFAULT NULL,
    reference_id INTEGER     DEFAULT NULL,
    content      TEXT        DEFAULT NULL,
    is_read      SMALLINT    DEFAULT 0,
    created_at   TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_notif_user   ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notif_unread ON notifications(user_id, is_read);

-- statuses
CREATE TABLE IF NOT EXISTS statuses (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER     NOT NULL,
    media_url  TEXT        NOT NULL,
    media_type VARCHAR(10) NOT NULL,
    caption    TEXT        DEFAULT NULL,
    created_at TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP   DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_status_user    ON statuses(user_id);
CREATE INDEX IF NOT EXISTS idx_status_expires ON statuses(expires_at);

-- status_views
CREATE TABLE IF NOT EXISTS status_views (
    id        SERIAL PRIMARY KEY,
    status_id INTEGER   NOT NULL,
    user_id   INTEGER   NOT NULL,
    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (status_id, user_id)
);

-- reels
CREATE TABLE IF NOT EXISTS reels (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER   NOT NULL,
    video_url  TEXT      NOT NULL,
    caption    TEXT      DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_reel_user ON reels(user_id);

-- reel_likes
CREATE TABLE IF NOT EXISTS reel_likes (
    id         SERIAL PRIMARY KEY,
    reel_id    INTEGER   NOT NULL,
    user_id    INTEGER   NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (reel_id, user_id)
);

-- reel_comments
CREATE TABLE IF NOT EXISTS reel_comments (
    id         SERIAL PRIMARY KEY,
    reel_id    INTEGER   NOT NULL,
    user_id    INTEGER   NOT NULL,
    comment    TEXT      NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rc_reel ON reel_comments(reel_id);

-- songs
CREATE TABLE IF NOT EXISTS songs (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER      NOT NULL,
    audio_url  TEXT         NOT NULL,
    title      VARCHAR(200) DEFAULT NULL,
    artist     VARCHAR(200) DEFAULT NULL,
    cover_url  TEXT         DEFAULT NULL,
    created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_song_user ON songs(user_id);

-- song_likes
CREATE TABLE IF NOT EXISTS song_likes (
    id         SERIAL PRIMARY KEY,
    song_id    INTEGER   NOT NULL,
    user_id    INTEGER   NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (song_id, user_id)
);

-- follows
CREATE TABLE IF NOT EXISTS follows (
    id           SERIAL PRIMARY KEY,
    follower_id  INTEGER   NOT NULL,
    following_id INTEGER   NOT NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (follower_id, following_id)
);
CREATE INDEX IF NOT EXISTS idx_follower  ON follows(follower_id);
CREATE INDEX IF NOT EXISTS idx_following ON follows(following_id);

-- blocks
CREATE TABLE IF NOT EXISTS blocks (
    id         SERIAL PRIMARY KEY,
    blocker_id INTEGER   NOT NULL,
    blocked_id INTEGER   NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (blocker_id, blocked_id)
);
CREATE INDEX IF NOT EXISTS idx_blocker ON blocks(blocker_id);
CREATE INDEX IF NOT EXISTS idx_blocked ON blocks(blocked_id);

-- posts
CREATE TABLE IF NOT EXISTS posts (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER     NOT NULL,
    media_url  TEXT        NOT NULL,
    media_type VARCHAR(10) NOT NULL,
    caption    TEXT        DEFAULT NULL,
    created_at TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_post_user ON posts(user_id);

-- post_likes
CREATE TABLE IF NOT EXISTS post_likes (
    id         SERIAL PRIMARY KEY,
    post_id    INTEGER   NOT NULL,
    user_id    INTEGER   NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (post_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_pl_post ON post_likes(post_id);

-- post_comments
CREATE TABLE IF NOT EXISTS post_comments (
    id         SERIAL PRIMARY KEY,
    post_id    INTEGER   NOT NULL,
    user_id    INTEGER   NOT NULL,
    comment    TEXT      NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pc_post ON post_comments(post_id);
