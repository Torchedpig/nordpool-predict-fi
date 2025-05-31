\
import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from rich import print

# Add project root to Python path to allow direct script execution
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from util.sql import get_db_columns, db_update
# Removed db_query_all as it's not used in this script anymore
from util.fmi import get_history # Using the existing get_history
from util.logger import logger

# Load environment variables from .env.local
# Ensure this path is correct if the script is run from elsewhere or project_root is different
env_path = os.path.join(project_root, '.env.local')
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    logger.warning(f".env.local not found at {env_path}. FMI IDs might not be loaded if not set in environment.")

def get_fmi_ids_from_env():
    """Fetches FMI station IDs from environment variables."""
    fmisid_ws_env = os.getenv('FMISID_WS')
    fmisid_t_env = os.getenv('FMISID_T')
    
    ws_ids = []
    if fmisid_ws_env:
        ws_ids = ['ws_' + id.strip() for id in fmisid_ws_env.split(',')]
        
    t_ids = []
    if fmisid_t_env:
        t_ids = ['t_' + id.strip() for id in fmisid_t_env.split(',')]
        
    return ws_ids, t_ids

def backfill_fmi_station_data(db_path, fmisid_with_prefix, fmi_param_name, start_backfill_date_str, end_backfill_date_str=None):
    """
    Fetches historical data for a single FMI station and updates the database.

    Args:
        db_path (str): Path to the SQLite database.
        fmisid_with_prefix (str): FMI station ID with 'ws_' or 't_' prefix (e.g., 'ws_101784').
        fmi_param_name (str): FMI parameter name (e.g., 'WS_PT1H_AVG' or 'TA_PT1H_AVG').
        start_backfill_date_str (str): Start date for backfilling (YYYY-MM-DD).
        end_backfill_date_str (str, optional): End date for backfilling (YYYY-MM-DD). 
                                            If None, defaults to yesterday.
    """
    fmisid = fmisid_with_prefix.split('_')[1]
    logger.info(f"Backfilling data for FMI station: {fmisid_with_prefix} ({fmi_param_name}) from {start_backfill_date_str} to {end_backfill_date_str or 'yesterday'}")

    current_start_date = datetime.strptime(start_backfill_date_str, '%Y-%m-%d')
    final_end_date_dt = datetime.strptime(end_backfill_date_str, '%Y-%m-%d') if end_backfill_date_str else datetime.utcnow() - timedelta(days=1)
    
    all_station_history_df = pd.DataFrame()

    while current_start_date <= final_end_date_dt:
        # Determine end of the current chunk (e.g., end of month, or not exceeding final_end_date_dt)
        # Using 28-day chunks for simplicity and to avoid month-end complexities, adjust if FMI allows full months
        current_chunk_end_date = current_start_date + timedelta(days=27) 
        if current_chunk_end_date > final_end_date_dt:
            current_chunk_end_date = final_end_date_dt
        
        current_start_date_str = current_start_date.strftime('%Y-%m-%d')
        current_chunk_end_date_str = current_chunk_end_date.strftime('%Y-%m-%d')

        logger.info(f"Fetching chunk for {fmisid_with_prefix}: {current_start_date_str} to {current_chunk_end_date_str}")

        try:
            # Fetch historical data using util.fmi.get_history for the current chunk
            history_df_chunk = get_history(fmisid, current_start_date_str, [fmi_param_name], end_date=current_chunk_end_date_str)
            
            if history_df_chunk.empty:
                logger.warning(f"No historical data returned for {fmisid_with_prefix} for chunk {current_start_date_str} to {current_chunk_end_date_str}. This might indicate a bad station ID or no data for the period.")
                # If a specific chunk is empty, we can log it and continue to the next.
                # If all chunks for a station ID are empty, it suggests a persistent issue with the ID.
            else:
                # Rename the fetched parameter column to the FMI ID with prefix
                history_df_chunk.rename(columns={fmi_param_name: fmisid_with_prefix}, inplace=True)
                history_df_chunk['timestamp'] = pd.to_datetime(history_df_chunk['timestamp'], utc=True)
                
                # Select only timestamp and the FMI station column
                history_df_chunk_to_append = history_df_chunk[['timestamp', fmisid_with_prefix]].copy()
                all_station_history_df = pd.concat([all_station_history_df, history_df_chunk_to_append], ignore_index=True)

        except Exception as e: # Catch exceptions from get_history (e.g., network issues, API errors)
            logger.error(f"Error fetching history for {fmisid_with_prefix} (chunk {current_start_date_str} to {current_chunk_end_date_str}): {e}. Skipping this station.")
            return # Skip backfilling for this entire station if a critical error occurs during any chunk fetch

        # Move to the next chunk
        current_start_date = current_chunk_end_date + timedelta(days=1)

    if all_station_history_df.empty:
        logger.warning(f"No historical data successfully fetched for {fmisid_with_prefix} for the entire period {start_backfill_date_str} to {end_backfill_date_str or 'yesterday'}. Station might be invalid or data unavailable.")
        return

    logger.info(f"Updating database with {len(all_station_history_df)} total records for {fmisid_with_prefix}.")
    
    # Ensure timestamp is a column for db_update
    if all_station_history_df.index.name == 'timestamp':
        all_station_history_df.reset_index(inplace=True)

    # Ensure no duplicate timestamps for the same station before updating
    all_station_history_df.drop_duplicates(subset=['timestamp', fmisid_with_prefix], keep='last', inplace=True)


    inserted_rows, updated_rows = db_update(db_path, all_station_history_df) 
    logger.info(f"Backfill for {fmisid_with_prefix}: {len(inserted_rows)} rows inserted, {len(updated_rows)} rows updated.")


def check_and_perform_backfill(): # Renamed from main
    # Determine project_root dynamically for flexibility
    current_script_path = os.path.dirname(os.path.abspath(__file__))
    project_root_path = os.path.abspath(os.path.join(current_script_path, '..'))

    db_path_env = os.getenv('DB_PATH', 'data/prediction.db')
    if not os.path.isabs(db_path_env): # Ensure db_path is absolute
        db_path = os.path.join(project_root_path, db_path_env)
    else:
        db_path = db_path_env
        
    # Ensure .env.local is loaded if this function is called externally
    # This is a bit redundant if called from main script that already loaded .env
    # but good for standalone robustness or direct calls.
    env_path_check = os.path.join(project_root_path, '.env.local')
    if not os.getenv('FMISID_WS') and not os.getenv('FMISID_T'): # Check if FMI IDs are loaded
        if os.path.exists(env_path_check):
            load_dotenv(env_path_check)
        else:
            logger.warning(f".env.local not found at {env_path_check} during check_and_perform_backfill. FMI IDs might not be loaded.")


    logger.info(f"Starting FMI data backfill check for database: {db_path}")

    env_ws_ids, env_t_ids = get_fmi_ids_from_env()
    all_env_fmi_ids = set(env_ws_ids + env_t_ids)

    if not all_env_fmi_ids:
        logger.info("No FMI station IDs found in .env.local. Skipping backfill process.")
        return False # Indicate no backfill was attempted or needed due to no IDs

    logger.info(f"FMI Stations in .env.local: {all_env_fmi_ids}")

    db_columns = get_db_columns(db_path)
    # If db_columns is empty, it means the DB or table doesn't exist.
    # db_update will create it, so we proceed.

    fmi_columns_in_db = {col for col in db_columns if col.startswith('ws_') or col.startswith('t_')}
    logger.info(f"FMI-related columns currently in '{db_path}': {fmi_columns_in_db}")

    new_fmi_ids_to_backfill = all_env_fmi_ids - fmi_columns_in_db
    
    if not new_fmi_ids_to_backfill:
        logger.info("No new FMI stations found in .env.local that are not already in the database. Nothing to backfill.")
        return False # Indicate no backfill was performed

    logger.info(f"New FMI Stations to backfill: {new_fmi_ids_to_backfill}")

    start_backfill_date_str = "2023-01-01"
    end_backfill_date = datetime.utcnow() - timedelta(days=1)
    end_backfill_date_str = end_backfill_date.strftime('%Y-%m-%d')

    backfill_performed = False
    for fmisid_with_prefix in new_fmi_ids_to_backfill:
        fmi_param_name = ''
        if fmisid_with_prefix.startswith('ws_'):
            fmi_param_name = 'WS_PT1H_AVG'
        elif fmisid_with_prefix.startswith('t_'):
            fmi_param_name = 'TA_PT1H_AVG'
        else:
            logger.warning(f"Unknown prefix for FMI ID: {fmisid_with_prefix}. Skipping.")
            continue
        
        backfill_fmi_station_data(db_path, fmisid_with_prefix, fmi_param_name, start_backfill_date_str, end_backfill_date_str)
        backfill_performed = True

    if backfill_performed:
        logger.info("FMI data backfill process completed for new stations.")
    return backfill_performed # Indicate whether backfill operations were run

if __name__ == "__main__":
    check_and_perform_backfill()
