-- Initialize database --

CREATE DATABASE IF NOT EXISTS ForumAnnotator;
USE ForumAnnotator;

-- User table --

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

-- Forum data tables --

DROP TABLE IF EXISTS `threads`;
CREATE TABLE IF NOT EXISTS `threads` (
    thread_id INTEGER PRIMARY KEY AUTO_INCREMENT,
    mongoid TEXT NOT NULL,
    creator TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    comment_count INTEGER NOT NULL,
    first_post_id INTEGER DEFAULT 0
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS `posts`;
CREATE TABLE IF NOT EXISTS `posts` (
    post_id INTEGER PRIMARY KEY AUTO_INCREMENT,
    thread_id INTEGER NOT NULL,
    mongoid TEXT NOT NULL,
    author_id INTEGER NOT NULL,
    author_username TEXT NOT NULL,
    body TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
    level INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    parent_post_id INTEGER
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4;

-- Annotation tables --

DROP TABLE IF EXISTS `tasks`;
CREATE TABLE `tasks` (
    task_id INTEGER PRIMARY KEY AUTO_INCREMENT,
    title TEXT NOT NULL,
    label TEXT NOT NULL,
    display TEXT NOT NULL,
    prompt TEXT NOT NULL,
    type TEXT NOT NULL,
    options TEXT NOT NULL,
    restrictions TEXT NOT NULL,
    allow_comments BOOLEAN NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS `assignments`;
CREATE TABLE `assignments` (
    assn_id INTEGER PRIMARY KEY AUTO_INCREMENT,
    task_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    thread_id INTEGER NOT NULL,
    next_post_id INTEGER DEFAULT NULL,
    done INTEGER DEFAULT 1,
    finished BOOLEAN NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS `codes`;
CREATE TABLE `codes` (
    code_id INTEGER PRIMARY KEY AUTO_INCREMENT,
    user_id INTEGER NOT NULL,
    post_id INTEGER NOT NULL,
    assn_id INTEGER NOT NULL,
    code_value TEXT,
    targets TEXT DEFAULT NULL,
    comment TEXT DEFAULT NULL,
    active INTEGER DEFAULT 1
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS `revised`;
CREATE TABLE `revised` LIKE `codes`;
