USE ForumAnnotator;

DELIMITER //

-- Total number of posts in a thread --
DROP FUNCTION IF EXISTS total_posts//
CREATE FUNCTION total_posts (thread_id TEXT)
RETURNS INT
DETERMINISTIC
BEGIN
    SELECT count(*) INTO @posts_count FROM threads WHERE `comment_thread_id` = thread_id;
    RETURN @posts_count;
END//

-- Total posts completed for a given assignment --
DROP FUNCTION IF EXISTS done_posts//
CREATE FUNCTION done_posts (this_assn_id INT)
RETURNS INT
DETERMINISTIC
BEGIN
    SELECT done INTO @done_count FROM assignments WHERE `assn_id` = this_assn_id;
    RETURN @done_count;
END//

-- Get title of thread --
DROP FUNCTION IF EXISTS thread_title//
CREATE FUNCTION thread_title (thread_id TEXT)
RETURNS TEXT
DETERMINISTIC
BEGIN
    SELECT title INTO @title_text
    FROM threads
    WHERE `mongoid` = thread_id;
    RETURN @title_text;
END//

-- Set thread finished indicator field --
DROP PROCEDURE IF EXISTS set_finished//
CREATE PROCEDURE set_finished(this_assn_id INT)
DETERMINISTIC
BEGIN
    UPDATE assignments SET finished = 1 WHERE `assn_id` = this_assn_id;
END//


DELIMITER ;
