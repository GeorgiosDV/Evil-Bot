import sqlite3
from sqlite3 import Error
import json
import config
import logging

logger = logging.getLogger('evil_bot')


def create_connection():
    try:
        conn = sqlite3.connect(config.DATABASE_NAME)
        return conn
    except Error as e:
        logger.error(f"Error connecting to database: {e}", exc_info=True)
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ensure_server_row(cursor, server_id):
    cursor.execute('''
        INSERT OR IGNORE INTO server_settings (
            server_id, system_prompt, trigger_words,
            random_responses_enabled, random_response_chance,
            channel_whitelist, model_name
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        server_id,
        config.DEFAULT_PERSONA,
        json.dumps(config.DEFAULT_TRIGGER_WORDS),
        config.DEFAULT_RANDOM_ENABLED,
        config.DEFAULT_RANDOM_CHANCE,
        '[]',
        '',
    ))


# ── Server settings ───────────────────────────────────────────────────────────

def get_server_settings(server_id):
    logger.debug(f"Getting server settings for server_id: {server_id}")
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            _ensure_server_row(c, server_id)
            conn.commit()
            c.execute('''
                SELECT system_prompt, trigger_words, random_responses_enabled,
                       random_response_chance, channel_whitelist, model_name
                FROM server_settings WHERE server_id = ?
            ''', (server_id,))
            result = c.fetchone()
            if result:
                return {
                    'system_prompt': result[0],
                    'trigger_words': json.loads(result[1]),
                    'random_responses_enabled': bool(result[2]),
                    'random_response_chance': result[3],
                    'channel_whitelist': json.loads(result[4]),
                    'model_name': result[5] or config.MODEL_NAME,
                }
        except Error as e:
            logger.error(f"Error getting server settings: {e}", exc_info=True)
        finally:
            conn.close()
    logger.error("Failed to get server settings")
    return None


def reset_server_settings(server_id):
    logger.info(f"Resetting server settings for server_id: {server_id}")
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            _ensure_server_row(c, server_id)
            c.execute('''
                UPDATE server_settings
                SET system_prompt = ?, trigger_words = ?,
                    random_responses_enabled = ?, random_response_chance = ?,
                    channel_whitelist = ?, model_name = ?
                WHERE server_id = ?
            ''', (
                config.DEFAULT_PERSONA,
                json.dumps(config.DEFAULT_TRIGGER_WORDS),
                config.DEFAULT_RANDOM_ENABLED,
                config.DEFAULT_RANDOM_CHANCE,
                '[]',
                '',
                server_id,
            ))
            conn.commit()
            return True
        except Error as e:
            logger.error(f"Error resetting server settings: {e}", exc_info=True)
            return False
        finally:
            conn.close()
    return False


# ── Server prompt ─────────────────────────────────────────────────────────────

def get_server_prompt(server_id):
    if server_id is None:
        return config.DEFAULT_PERSONA
    settings = get_server_settings(server_id)
    return settings['system_prompt'] if settings else config.DEFAULT_PERSONA


def set_server_prompt(server_id, prompt):
    logger.info(f"Setting server prompt for server_id: {server_id}")
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            _ensure_server_row(c, server_id)
            c.execute('UPDATE server_settings SET system_prompt = ? WHERE server_id = ?', (prompt, server_id))
            conn.commit()
            logger.info("Server prompt updated successfully")
            return c.rowcount > 0
        except Error as e:
            logger.error(f"Error setting server prompt: {e}", exc_info=True)
            return False
        finally:
            conn.close()
    return False


# ── DM prompt ─────────────────────────────────────────────────────────────────

def get_dm_prompt(user_id):
    logger.debug(f"Getting DM prompt for user_id: {user_id}")
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            c.execute('SELECT system_prompt FROM dm_settings WHERE user_id = ?', (user_id,))
            result = c.fetchone()
            return result[0] if result else config.DEFAULT_PERSONA
        except Error as e:
            logger.error(f"Error getting DM prompt: {e}", exc_info=True)
            return config.DEFAULT_PERSONA
        finally:
            conn.close()
    return config.DEFAULT_PERSONA


def set_dm_prompt(user_id, prompt):
    logger.info(f"Setting DM prompt for user_id: {user_id}")
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            c.execute('INSERT OR REPLACE INTO dm_settings (user_id, system_prompt) VALUES (?, ?)', (user_id, prompt))
            conn.commit()
            return True
        except Error as e:
            logger.error(f"Error setting DM prompt: {e}", exc_info=True)
            return False
        finally:
            conn.close()
    return False


# ── Trigger words ─────────────────────────────────────────────────────────────

def set_trigger_words(server_id, words):
    logger.info(f"Setting trigger words for server_id: {server_id}")
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            _ensure_server_row(c, server_id)
            c.execute('UPDATE server_settings SET trigger_words = ? WHERE server_id = ?', (json.dumps(words), server_id))
            conn.commit()
            return c.rowcount > 0
        except Error as e:
            logger.error(f"Error setting trigger words: {e}", exc_info=True)
            return False
        finally:
            conn.close()
    return False


# ── Random responses ──────────────────────────────────────────────────────────

def set_random_responses(server_id, enabled):
    logger.info(f"Setting random responses for server_id: {server_id} to {enabled}")
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            _ensure_server_row(c, server_id)
            c.execute('UPDATE server_settings SET random_responses_enabled = ? WHERE server_id = ?', (enabled, server_id))
            conn.commit()
            return c.rowcount > 0
        except Error as e:
            logger.error(f"Error setting random responses: {e}", exc_info=True)
            return False
        finally:
            conn.close()
    return False


def set_random_chance(server_id, chance):
    logger.info(f"Setting random chance for server_id: {server_id} to {chance}%")
    if not 1 <= chance <= 100:
        return False
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            _ensure_server_row(c, server_id)
            c.execute('UPDATE server_settings SET random_response_chance = ? WHERE server_id = ?', (chance, server_id))
            conn.commit()
            return c.rowcount > 0
        except Error as e:
            logger.error(f"Error setting random chance: {e}", exc_info=True)
            return False
        finally:
            conn.close()
    return False


# ── Channel whitelist ─────────────────────────────────────────────────────────

def set_channel_whitelist(server_id, channel_ids):
    logger.info(f"Setting channel whitelist for server_id: {server_id}")
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            _ensure_server_row(c, server_id)
            c.execute('UPDATE server_settings SET channel_whitelist = ? WHERE server_id = ?', (json.dumps(channel_ids), server_id))
            conn.commit()
            return c.rowcount > 0
        except Error as e:
            logger.error(f"Error setting channel whitelist: {e}", exc_info=True)
            return False
        finally:
            conn.close()
    return False


# ── Model ─────────────────────────────────────────────────────────────────────

def get_server_model(server_id):
    settings = get_server_settings(server_id)
    if settings and settings['model_name']:
        return settings['model_name']
    return config.MODEL_NAME


def set_server_model(server_id, model_name):
    logger.info(f"Setting model for server_id: {server_id} to {model_name}")
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            _ensure_server_row(c, server_id)
            c.execute('UPDATE server_settings SET model_name = ? WHERE server_id = ?', (model_name, server_id))
            conn.commit()
            return c.rowcount > 0
        except Error as e:
            logger.error(f"Error setting server model: {e}", exc_info=True)
            return False
        finally:
            conn.close()
    return False


# ── Presets ───────────────────────────────────────────────────────────────────

def get_presets(server_id):
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            c.execute('SELECT name, prompt FROM server_presets WHERE server_id = ? ORDER BY name', (server_id,))
            return [{'name': r[0], 'prompt': r[1]} for r in c.fetchall()]
        except Error as e:
            logger.error(f"Error getting presets: {e}", exc_info=True)
            return []
        finally:
            conn.close()
    return []


def save_preset(server_id, name, prompt):
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            c.execute('INSERT OR REPLACE INTO server_presets (server_id, name, prompt) VALUES (?, ?, ?)', (server_id, name, prompt))
            conn.commit()
            return True
        except Error as e:
            logger.error(f"Error saving preset: {e}", exc_info=True)
            return False
        finally:
            conn.close()
    return False


def load_preset(server_id, name):
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            c.execute('SELECT prompt FROM server_presets WHERE server_id = ? AND name = ?', (server_id, name))
            result = c.fetchone()
            return result[0] if result else None
        except Error as e:
            logger.error(f"Error loading preset: {e}", exc_info=True)
            return None
        finally:
            conn.close()
    return None


def delete_preset(server_id, name):
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            c.execute('DELETE FROM server_presets WHERE server_id = ? AND name = ?', (server_id, name))
            conn.commit()
            return c.rowcount > 0
        except Error as e:
            logger.error(f"Error deleting preset: {e}", exc_info=True)
            return False
        finally:
            conn.close()
    return False


# ── Prompt history ────────────────────────────────────────────────────────────

def add_prompt_history(server_id, prompt, set_by):
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            c.execute('INSERT INTO prompt_history (server_id, prompt, set_by) VALUES (?, ?, ?)', (server_id, prompt, set_by))
            # Prune oldest entries beyond the cap
            c.execute('''
                DELETE FROM prompt_history
                WHERE server_id = ? AND id NOT IN (
                    SELECT id FROM prompt_history
                    WHERE server_id = ?
                    ORDER BY set_at DESC
                    LIMIT ?
                )
            ''', (server_id, server_id, config.MAX_PROMPT_HISTORY))
            conn.commit()
            return True
        except Error as e:
            logger.error(f"Error adding prompt history: {e}", exc_info=True)
            return False
        finally:
            conn.close()
    return False


def get_prompt_history(server_id, limit=10):
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            c.execute('''
                SELECT id, prompt, set_at, set_by
                FROM prompt_history
                WHERE server_id = ?
                ORDER BY set_at DESC
                LIMIT ?
            ''', (server_id, limit))
            return [{'id': r[0], 'prompt': r[1], 'set_at': r[2], 'set_by': r[3]} for r in c.fetchall()]
        except Error as e:
            logger.error(f"Error getting prompt history: {e}", exc_info=True)
            return []
        finally:
            conn.close()
    return []


def get_prompt_history_entry(server_id, entry_id):
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            c.execute(
                'SELECT id, prompt, set_at, set_by FROM prompt_history WHERE server_id = ? AND id = ?',
                (server_id, entry_id),
            )
            r = c.fetchone()
            return {'id': r[0], 'prompt': r[1], 'set_at': r[2], 'set_by': r[3]} if r else None
        except Error as e:
            logger.error(f"Error getting prompt history entry: {e}", exc_info=True)
            return None
        finally:
            conn.close()
    return None


# ── Init ──────────────────────────────────────────────────────────────────────

def init_db():
    logger.info("Initializing database...")
    conn = create_connection()
    if conn is None:
        logger.error("Failed to create database connection")
        return
    try:
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS server_settings (
                server_id INTEGER PRIMARY KEY,
                system_prompt TEXT NOT NULL,
                trigger_words TEXT NOT NULL,
                random_responses_enabled BOOLEAN NOT NULL,
                random_response_chance INTEGER NOT NULL,
                channel_whitelist TEXT NOT NULL DEFAULT '[]',
                model_name TEXT NOT NULL DEFAULT ''
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS dm_settings (
                user_id INTEGER PRIMARY KEY,
                system_prompt TEXT NOT NULL
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS server_presets (
                server_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                prompt TEXT NOT NULL,
                PRIMARY KEY (server_id, name)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS prompt_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id INTEGER NOT NULL,
                prompt TEXT NOT NULL,
                set_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                set_by INTEGER NOT NULL
            )
        ''')

        # Migrations for existing databases that predate new columns
        for column, definition in [
            ('channel_whitelist', "TEXT NOT NULL DEFAULT '[]'"),
            ('model_name', "TEXT NOT NULL DEFAULT ''"),
        ]:
            try:
                c.execute(f'ALTER TABLE server_settings ADD COLUMN {column} {definition}')
                logger.info(f"Migration: added column '{column}' to server_settings")
            except Error:
                pass  # column already exists

        conn.commit()
        logger.info("Database initialized successfully")

    except Error as e:
        logger.error(f"Error initializing database: {e}", exc_info=True)
    finally:
        conn.close()
