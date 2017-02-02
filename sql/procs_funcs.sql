USE ForumAnnotator;

DELIMITER //

-- Total number of posts in a thread --
DROP FUNCTION IF EXISTS total_posts//
CREATE FUNCTION total_posts (in_thread_id TEXT)
RETURNS INT
DETERMINISTIC
BEGIN
    SELECT comment_count INTO @posts_count FROM threads WHERE `thread_id` = in_thread_id;
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
CREATE FUNCTION thread_title (in_thread_id TEXT)
RETURNS TEXT
DETERMINISTIC
BEGIN
    SELECT title INTO @title_text
    FROM threads
    WHERE `thread_id` = in_thread_id;
    RETURN @title_text;
END//

-- Set thread finished indicator field --
DROP PROCEDURE IF EXISTS set_finished//
CREATE PROCEDURE set_finished(this_assn_id INT)
DETERMINISTIC
BEGIN
    UPDATE assignments SET finished = 1 WHERE `assn_id` = this_assn_id;
END//

-- Set level of posts --
DROP PROCEDURE IF EXISTS set_levels//
CREATE PROCEDURE `set_levels`(this_thread_id INT, this_parent_post_id INT)
DETERMINISTIC
BEGIN
    DROP TABLE IF EXISTS posts_3;
    CREATE TEMPORARY TABLE IF NOT EXISTS posts_3 AS (
        SELECT post_id
        FROM posts
        WHERE thread_id = this_thread_id
        AND level = 3
        GROUP BY parent_post_id
        ORDER BY parent_post_id, post_id
    );

    DROP TABLE IF EXISTS posts_4;
    CREATE TEMPORARY TABLE IF NOT EXISTS posts_4 AS (
        SELECT post_id
        FROM posts
        WHERE thread_id = this_thread_id
        AND level = 3
        AND post_id NOT IN (SELECT * FROM posts_3)
    );

    UPDATE posts
    SET level = 4
    WHERE post_id IN (SELECT * FROM posts_4);
END//


DELIMITER ;
