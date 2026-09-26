"""
database/db.py — Enhanced Database connection and transaction manager for Jeevan Setu.
Provides thread-safe connection pooling, auto-reconnection, stale socket recovery,
and transactional safety.
"""

import time
import threading
from contextlib import contextmanager
import mysql.connector
from mysql.connector import Error, errorcode, pooling
from config import get_config


class Database:
    """Singleton database connection and transaction manager with auto-recovery."""

    _instance = None
    _lock = threading.Lock()
    _pool = None

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def _get_connection_pool(self):
        """Initialize or return the MySQL connection pool."""
        if self._pool is None:
            with self._lock:
                if self._pool is None:
                    config = get_config()
                    try:
                        self._pool = pooling.MySQLConnectionPool(
                            pool_name="jeevan_setu_pool",
                            pool_size=16,
                            pool_reset_session=True,
                            host=config.DB_HOST,
                            port=config.DB_PORT,
                            user=config.DB_USER,
                            password=config.DB_PASSWORD,
                            database=config.DB_NAME,
                            autocommit=False,
                            connect_timeout=10
                        )
                    except Error as e:
                        print(f"[DB POOL INIT WARN] Pool initialization deferred: {e}")
                        self._pool = None
        return self._pool

    def get_connection(self):
        """Get a validated database connection from pool or direct connect."""
        config = get_config()
        pool = self._get_connection_pool()

        if pool:
            try:
                conn = pool.get_connection()
                # Test connection liveness
                if not conn.is_connected():
                    conn.ping(reconnect=True, attempts=3, delay=1)
                return conn
            except Error as e:
                # If pool exhausted or dropped, fall back to direct connection
                print(f"[DB POOL GET WARN] {e} - falling back to direct connection")

        # Direct fresh connection fallback
        try:
            conn = mysql.connector.connect(
                host=config.DB_HOST,
                port=config.DB_PORT,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                database=config.DB_NAME,
                autocommit=False,
                connect_timeout=10
            )
            return conn
        except Error as e:
            print(f"[DB ERROR] Failed to connect to MySQL database: {e}")
            raise

    def execute_query(self, query, params=None, fetch=False, cursor_dict=True, retries=1):
        """
        Execute a single SQL query with automatic reconnection retry.
        Supports fetch=True (fetchall), fetch='one' (fetchone), or write operations (lastrowid).
        """
        attempt = 0
        while attempt <= retries:
            conn = None
            cursor = None
            try:
                conn = self.get_connection()
                cursor = conn.cursor(dictionary=cursor_dict, buffered=True)
                cursor.execute(query, params or ())

                if fetch is True or fetch == 'all':
                    result = cursor.fetchall()
                    return result
                elif fetch == 'one':
                    result = cursor.fetchone()
                    return result
                else:
                    conn.commit()
                    return cursor.lastrowid or cursor.rowcount

            except (Error, Exception) as e:
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass

                # Check if error is a recoverable disconnection
                is_connection_error = False
                if isinstance(e, Error):
                    if e.errno in (
                        errorcode.CR_SERVER_GONE_ERROR,
                        errorcode.CR_SERVER_LOST,
                        errorcode.ER_CON_COUNT_ERROR,
                        2006, 2013, 2055
                    ) or 'gone away' in str(e).lower() or 'lost connection' in str(e).lower():
                        is_connection_error = True

                if is_connection_error and attempt < retries:
                    attempt += 1
                    print(f"[DB WARN] Lost MySQL connection. Reconnecting and retrying ({attempt}/{retries})...")
                    time.sleep(0.2)
                    continue

                print(f"[DB ERROR] Query execution failed: {e} | Query: {query[:120]}")
                raise

            finally:
                if cursor:
                    try:
                        cursor.close()
                    except Exception:
                        pass
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

    def execute_many(self, query, data_list, retries=1):
        """Execute a batch query with multiple parameter rows."""
        if not data_list:
            return 0

        attempt = 0
        while attempt <= retries:
            conn = None
            cursor = None
            try:
                conn = self.get_connection()
                cursor = conn.cursor(buffered=True)
                cursor.executemany(query, data_list)
                conn.commit()
                return cursor.rowcount

            except Error as e:
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass

                if attempt < retries and (e.errno in (2006, 2013, 2055) or 'gone away' in str(e).lower()):
                    attempt += 1
                    print(f"[DB WARN] Batch connection lost. Retrying ({attempt}/{retries})...")
                    time.sleep(0.2)
                    continue

                print(f"[DB ERROR] Batch query failed: {e}")
                raise

            finally:
                if cursor:
                    try:
                        cursor.close()
                    except Exception:
                        pass
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

    @contextmanager
    def transaction(self):
        """
        Context manager for executing multiple statements in a single transaction.
        Yields a dictionary cursor. Commits on successful block completion,
        rolls back on exception.
        """
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            print(f"[DB TRANSACTION ERROR] Rolled back transaction: {e}")
            raise
        finally:
            try:
                cursor.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass

    def close(self):
        """Close pool connections if applicable."""
        self._pool = None
        print("[DB] Connection pool reset.")


# Global singleton instance
db = Database()

# Module-level convenience functions
def get_db():
    """Return global db instance."""
    return db

def get_connection():
    """Return a database connection."""
    return db.get_connection()

def execute_query(query, params=None, fetch=False, cursor_dict=True):
    """Execute a query using global database manager."""
    return db.execute_query(query, params, fetch=fetch, cursor_dict=cursor_dict)

def execute_many(query, data_list):
    """Execute batch queries using global database manager."""
    return db.execute_many(query, data_list)

def transaction():
    """Execute transactional statements using global database manager."""
    return db.transaction()

