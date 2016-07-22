DROP TABLE IF EXISTS `assignments`;
CREATE TABLE `assignments` (
	id integer primary key autoincrement,
	user_id integer not null,
	thread_id integer not null,
	next_post integer default null,
	finished boolean not null
);

DROP TABLE IF EXISTS `threads`;
CREATE TABLE `threads` (
	id integer primary key autoincrement,
	author_id integer not null,
	author_username text not null,
	X_type text not null,
	title text not null,
	body longtext not null,
	thread_type text not null,
	commentable_id text not null,
	comment_count integer not null,
	pinned boolean,
	created_at integer not null,
	updated_at integer not null,
	anonymous boolean,
	parent_ids text,
	comment_thread_id integer not null,
	mongoid integer not null,
	level integer not null,
	finished boolean not null
);

-- DROP TABLE IF EXISTS `codes`;
-- CREATE TABLE `codes` (
-- 	# TODO
-- );

DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
	id integer primary key autoincrement,
	username text not null,
	first_name text not null,
	last_name text not null,
	email text not null,
	pass_hash text not null,
	superuser boolean not null
);