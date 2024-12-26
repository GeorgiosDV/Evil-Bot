import sqlite3
from sqlite3 import Error
import json
import config
import logging

logger = logging.getLogger('evil_bot')

def create_connection():
    try:
        logger.debug(f"Connecting to database: {config.DATABASE_NAME}")
        conn = sqlite3.connect(config.DATABASE_NAME)
        return conn
    except Error as e:
        logger.error(f"Error connecting to database: {e}", exc_info=True)
        return None

def get_server_prompt(server_id):
    logger.debug(f"Getting server prompt for server_id: {server_id}")
    if server_id is None:
        logger.debug("No server_id provided, returning default persona")
        return config.DEFAULT_PERSONA
    settings = get_server_settings(server_id)
    result = settings['system_prompt'] if settings else config.DEFAULT_PERSONA
    logger.debug(f"Retrieved prompt: {result[:50]}...")
    return result

def get_dm_prompt(user_id):
    logger.debug(f"Getting DM prompt for user_id: {user_id}")
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            c.execute('SELECT system_prompt FROM dm_settings WHERE user_id = ?', (user_id,))
            result = c.fetchone()
            prompt = result[0] if result else config.DEFAULT_PERSONA
            logger.debug(f"Retrieved DM prompt: {prompt[:50]}...")
            return prompt
        except Error as e:
            logger.error(f"Error getting DM prompt: {e}", exc_info=True)
            return config.DEFAULT_PERSONA
        finally:
            conn.close()
    logger.warning("No database connection, returning default persona")
    return config.DEFAULT_PERSONA

def set_dm_prompt(user_id, prompt):
    logger.info(f"Setting DM prompt for user_id: {user_id}")
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            c.execute('''
                INSERT OR REPLACE INTO dm_settings (user_id, system_prompt)
                VALUES (?, ?)
            ''', (user_id, prompt))
            conn.commit()
            logger.info("DM prompt set successfully")
            return True
        except Error as e:
            logger.error(f"Error setting DM prompt: {e}", exc_info=True)
            return False
        finally:
            conn.close()
    return False

def set_server_prompt(server_id, prompt):
    logger.info(f"Setting server prompt for server_id: {server_id}")
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            c.execute('''
                UPDATE server_settings 
                SET system_prompt = ?
                WHERE server_id = ?
            ''', (prompt, server_id))
            conn.commit()
            logger.info("Server prompt updated successfully")
            return True
        except Error as e:
            logger.error(f"Error setting server prompt: {e}", exc_info=True)
            return False
        finally:
            conn.close()
    return False

def reset_server_settings(server_id):
    logger.info(f"Resetting server settings for server_id: {server_id}")
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            c.execute('''
                UPDATE server_settings 
                SET system_prompt = ?,
                    trigger_words = ?,
                    random_responses_enabled = ?,
                    random_response_chance = ?
                WHERE server_id = ?
            ''', (
                config.DEFAULT_PERSONA,
                json.dumps(config.DEFAULT_TRIGGER_WORDS),
                config.DEFAULT_RANDOM_ENABLED,
                config.DEFAULT_RANDOM_CHANCE,
                server_id
            ))
            conn.commit()
            logger.info("Server settings reset successfully")
            return True
        except Error as e:
            logger.error(f"Error resetting server settings: {e}", exc_info=True)
            return False
        finally:
            conn.close()
    return False

def set_trigger_words(server_id, words):
    logger.info(f"Setting trigger words for server_id: {server_id}")
    logger.debug(f"New trigger words: {words}")
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            c.execute('''
                UPDATE server_settings 
                SET trigger_words = ?
                WHERE server_id = ?
            ''', (json.dumps(words), server_id))
            conn.commit()
            logger.info("Trigger words updated successfully")
            return True
        except Error as e:
            logger.error(f"Error setting trigger words: {e}", exc_info=True)
            return False
        finally:
            conn.close()
    return False

def set_random_responses(server_id, enabled):
    logger.info(f"Setting random responses for server_id: {server_id} to {enabled}")
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            c.execute('''
                UPDATE server_settings 
                SET random_responses_enabled = ?
                WHERE server_id = ?
            ''', (enabled, server_id))
            conn.commit()
            logger.info("Random responses setting updated successfully")
            return True
        except Error as e:
            logger.error(f"Error setting random responses: {e}", exc_info=True)
            return False
        finally:
            conn.close()
    return False

def set_random_chance(server_id, chance):
    logger.info(f"Setting random chance for server_id: {server_id} to {chance}%")
    if not 1 <= chance <= 100:
        logger.error(f"Invalid chance value: {chance}")
        return False
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            c.execute('''
                UPDATE server_settings 
                SET random_response_chance = ?
                WHERE server_id = ?
            ''', (chance, server_id))
            conn.commit()
            logger.info("Random chance updated successfully")
            return True
        except Error as e:
            logger.error(f"Error setting random chance: {e}", exc_info=True)
            return False
        finally:
            conn.close()
    return False

def init_db():
    logger.info("Initializing database...")
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            
            logger.debug("Creating server_settings table...")
            c.execute('''
                CREATE TABLE IF NOT EXISTS server_settings (
                    server_id INTEGER PRIMARY KEY,
                    system_prompt TEXT NOT NULL,
                    trigger_words TEXT NOT NULL,
                    random_responses_enabled BOOLEAN NOT NULL,
                    random_response_chance INTEGER NOT NULL
                )
            ''')
            
            logger.debug("Creating dm_settings table...")
            c.execute('''
                CREATE TABLE IF NOT EXISTS dm_settings (
                    user_id INTEGER PRIMARY KEY,
                    system_prompt TEXT NOT NULL
                )
            ''')
            
            conn.commit()
            logger.info("Database tables created successfully")

            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = c.fetchall()
            logger.info(f"Existing tables: {[table[0] for table in tables]}")
            
        except Error as e:
            logger.error(f"Error initializing database: {e}", exc_info=True)
        finally:
            conn.close()
    else:
        logger.error("Failed to create database connection")

def get_server_settings(server_id):
    logger.debug(f"Getting server settings for server_id: {server_id}")
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            logger.debug("Inserting default values if not exist...")
            c.execute('''
                INSERT OR IGNORE INTO server_settings (
                    server_id, system_prompt, trigger_words,
                    random_responses_enabled, random_response_chance
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                server_id,
                config.DEFAULT_PERSONA,
                json.dumps(config.DEFAULT_TRIGGER_WORDS),
                config.DEFAULT_RANDOM_ENABLED,
                config.DEFAULT_RANDOM_CHANCE
            ))
            conn.commit()

            c.execute('SELECT * FROM server_settings WHERE server_id = ?', (server_id,))
            result = c.fetchone()
            if result:
                settings = {
                    'system_prompt': result[1],
                    'trigger_words': json.loads(result[2]),
                    'random_responses_enabled': bool(result[3]),
                    'random_response_chance': result[4]
                }
                logger.debug(f"Retrieved settings: {settings}")
                return settings
        except Error as e:
            logger.error(f"Error getting server settings: {e}", exc_info=True)
        finally:
            conn.close()
    logger.error("Failed to get server settings")
    return None
