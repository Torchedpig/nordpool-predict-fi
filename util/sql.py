import sqlite3
import pandas as pd
import sys
import os
from rich import print
from .logger import logger

# A set of functions to work with the predictions SQLite database

# Suppress FutureWarning messages from pandas for now
import warnings
warnings.filterwarnings('ignore', category=FutureWarning)

def normalize_timestamp(ts):
    '''
    Converts a timestamp string into a datetime object, ensuring it is timezone-aware (UTC),
    and formats it as an ISO8601 string. This standardized format is crucial for consistency 
    across database operations, especially when dealing with the TIMESTAMP type in the schema.
    
    Parameters:
    - ts: A timestamp string that may or may not include timezone information.
    
    Returns:
    - A string representing the timestamp in ISO8601 format with UTC timezone information.
    '''
    # Convert to datetime object using pandas
    dt = pd.to_datetime(ts)
    
    # If the datetime object is naive (no timezone), localize it to UTC
    if dt.tzinfo is None:
        dt = dt.tz_localize('UTC')
    else:
        # If it already has a timezone, convert it to UTC
        dt = dt.tz_convert('UTC')
    
    # Format as ISO8601 string with timezone information
    return dt.isoformat()

def db_update(db_path, df):
    '''
    Update existing rows or insert new rows into the 'prediction' table in the specified SQLite database.
    The table and necessary columns are created dynamically if they don't exist.
    Returns two DataFrames: one containing inserted rows and another containing updated rows.
    '''
    # Ensure the directory for the database exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = None  # Initialize conn to None
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
    except sqlite3.Error as e:
        logger.info(f"SQLite connection error: {e}", exc_info=True)
        sys.exit(1)

    # Create prediction table if it doesn't exist with essential columns
    # FMI station related columns will be added dynamically
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prediction (
            timestamp TEXT PRIMARY KEY,
            "WindPowerCapacityMW" REAL,
            "NuclearPowerMW" REAL,
            "Price_cpkWh" REAL,
            "PricePredict_cpkWh" REAL
        )
    """)
    conn.commit() # Commit table creation

    # Get current columns in the prediction table
    cur.execute("PRAGMA table_info(prediction)")
    table_columns = [info[1] for info in cur.fetchall()]

    # Dynamically add new columns from the DataFrame if they don't exist in the table
    for col in df.columns:
        if col not in table_columns:
            # Assuming new columns for FMI data should be REAL type
            # Enclose column names in double quotes to handle special characters or keywords
            cur.execute(f'ALTER TABLE prediction ADD COLUMN "{col}" REAL')
            logger.info(f'Added column "{col}" to prediction table.')
    conn.commit() # Commit column additions

    updated_rows = pd.DataFrame()
    inserted_rows = pd.DataFrame()

    # Normalize timestamp in the dataframe before processing
    df['timestamp'] = df['timestamp'].apply(normalize_timestamp)

    for index, row in df.iterrows():
        # Timestamp is already normalized
        cur.execute("SELECT * FROM prediction WHERE timestamp=?", (row['timestamp'],))
        data = cur.fetchone()
        if data is not None:
            # Update existing row
            # Prepare set clause for all columns in the DataFrame row
            set_clauses = []
            values_to_update = []
            for col in df.columns:
                if pd.notnull(row[col]) and col != 'timestamp': # Don't update timestamp itself in SET
                    set_clauses.append(f'"{col}"=?')
                    values_to_update.append(row[col])
            
            if set_clauses: # Only execute update if there are columns to update
                values_to_update.append(row['timestamp']) # Add timestamp for WHERE clause
                cur.execute(f"UPDATE prediction SET {', '.join(set_clauses)} WHERE timestamp=?", tuple(values_to_update))
            updated_rows = pd.concat([updated_rows, df.loc[[index]]], ignore_index=True)
        else:
            # Insert new row
            cols = ', '.join(f'"{col}"' for col in df.columns)
            placeholders = ', '.join('?' * len(df.columns))
            cur.execute(f"INSERT INTO prediction ({cols}) VALUES ({placeholders})", tuple(row))
            inserted_rows = pd.concat([inserted_rows, df.loc[[index]]], ignore_index=True)

    conn.commit()
    conn.close()

    return inserted_rows, updated_rows

def db_query(db_path, df):
    '''
    Query the 'prediction' table in the specified SQLite database based on timestamps specified in the input DataFrame. Returns a DataFrame with the query results, sorted by timestamp.
    '''
    # Normalize timestamps in query dataframe
    if 'timestamp' not in df.columns:
        logger.info(f"Timestamp is not a column in the DataFrame")
    else:
        df['timestamp'] = df['timestamp'].apply(normalize_timestamp)

    try:
        conn = sqlite3.connect(db_path)
    except Exception as e:
        logger.info(f"Error preparing for SQLite query: {e}")
        sys.exit(1)
        
    result_frames = []  # List to store each chunk of dataframes
    for timestamp in df['timestamp']:
        # Timestamp is already normalized
        # Check if prediction table exists before querying
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prediction';")
        if cur.fetchone() is None:
            logger.info("Prediction table does not exist. Returning empty DataFrame.")
            conn.close()
            return pd.DataFrame()
        cur.close()

        data = pd.read_sql_query(f"SELECT * FROM prediction WHERE timestamp='{timestamp}'", conn)
        if not data.empty and not data.isna().all().all():  # Exclude empty dataframes and dataframes with all-NA entries
            result_frames.append(data)

    result = pd.concat(result_frames, ignore_index=True) if result_frames else pd.DataFrame()
    # logger.info(result)
    result = result.sort_values(by='timestamp', ascending=True)

    conn.close()

    return result

def db_query_all(db_path):
    '''
    Query all rows from the 'prediction' table in the specified SQLite database. Returns a DataFrame with the query results.
    '''
    conn = sqlite3.connect(db_path)
    # Check if prediction table exists before querying
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prediction';")
    if cur.fetchone() is None:
        logger.info("Prediction table does not exist. Returning empty DataFrame.")
        conn.close()
        return pd.DataFrame()
    cur.close()

    query = "SELECT * FROM prediction"
    data = pd.read_sql_query(query, conn)
    conn.close()
    return data

def get_db_columns(db_path, table_name="prediction"):
    """
    Retrieves the column names from a specified table in the SQLite database.

    Args:
        db_path (str): Path to the SQLite database file.
        table_name (str): Name of the table from which to fetch column names.

    Returns:
        list: A list of column names, or an empty list if the table
              doesn't exist or an error occurs.
    """
    if not os.path.exists(db_path):
        logger.info(f"Database file {db_path} does not exist. Returning empty list of columns.")
        return []

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
        if cursor.fetchone() is None:
            logger.info(f"Table '{table_name}' does not exist in {db_path}. Returning empty list of columns.")
            return []
            
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = [row[1] for row in cursor.fetchall()]
        return columns
    except sqlite3.Error as e:
        logger.error(f"SQLite error when fetching columns from {table_name} in {db_path}: {e}")
        return []
    finally:
        if conn:
            conn.close()

# Example usage (for testing, can be removed)
if __name__ == '__main__':
    # ...existing code...
    pass
