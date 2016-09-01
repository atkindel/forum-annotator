-- Initialize database --

CREATE DATABASE IF NOT EXISTS ForumAnnotator;
USE ForumAnnotator;

-- Table definitions --

DROP TABLE IF EXISTS `assignments`;
CREATE TABLE `assignments` (
    assn_id INTEGER PRIMARY KEY AUTO_INCREMENT,
    user_id INTEGER NOT NULL,
    thread_id TEXT NOT NULL,
    code_type TEXT NOT NULL,
    next_post TEXT DEFAULT NULL,
    done INTEGER DEFAULT 0,
    finished BOOLEAN NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS `threads`;
CREATE TABLE `threads` (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    author_id INTEGER NOT NULL,
    author_username TEXT NOT NULL,
    X_type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    thread_type TEXT NOT NULL,
    commentable_id TEXT NOT NULL,
    comment_count INTEGER NOT NULL,
    pinned BOOLEAN,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    anonymous BOOLEAN,
    parent_ids TEXT,
    comment_thread_id TEXT,
    mongoid TEXT NOT NULL,
    level INTEGER NOT NULL,
    finished BOOLEAN NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS `codes`;
CREATE TABLE `codes` (
    user_id INTEGER NOT NULL,
    post_id TEXT NOT NULL,
    code_type TEXT NOT NULL,
    code_value TEXT,
    comment TEXT
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    username TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL,
    pass_hash TEXT NOT NULL,
    superuser BOOLEAN NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
