"""
Trains an XGBoost model for wind power prediction using meteorological features.

Functions:
- preprocess_data: Preprocesses the input DataFrame for training.
- train_windpower_xgb: Trains an XGBoost model with the preprocessed data.

"""

import os
import sys
import json
import numpy as np
import pandas as pd
from typing import Tuple, List
from rich import print
from sklearn.model_selection import train_test_split
import xgboost as xgb
from .logger import logger

pd.options.mode.copy_on_write = True

def preprocess_data(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    # logger.info(f"Preprocess: Starting data preprocessing")

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['hour'] = df['timestamp'].dt.hour
    # df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24) # Keep commented
    # df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24) # Keep commented

    if 'WindPowerCapacityMW' in df.columns:
        df['WindPowerCapacityMW'] = df['WindPowerCapacityMW'].ffill()
    else:
        logger.error(f"'WindPowerCapacityMW' column not found.", exc_info=True)
        sys.exit(1)

    if 'WindPowerMW' in df.columns and 'WindPowerCapacityMW' in df.columns:
        df['WindProductionPercent'] = df['WindPowerMW'] / df['WindPowerCapacityMW']
    else:
        logger.error(f"'WindPowerMW' or 'WindPowerCapacityMW' column not found.", exc_info=True)
        sys.exit(1)

    # --- MODIFICATION START for selective FMI column usage ---
    fmisid_ws_str = os.getenv("FMISID_WS", "")
    fmisid_t_str = os.getenv("FMISID_T", "")

    # Get all potential ws/t columns from the DataFrame first
    all_df_ws_cols = [col for col in df.columns if col.startswith("ws_") or col.startswith("eu_ws_")]
    all_df_t_cols = [col for col in df.columns if col.startswith("t_")]

    fmisids_from_ws_env_list = [] # Stores the actual FMI IDs from FMISID_WS env var

    if fmisid_ws_str:
        fmisids_from_ws_env_list = [sid.strip() for sid in fmisid_ws_str.split(',') if sid.strip()]
        
        # Select ws_ columns: FMI stations from FMISID_WS + all eu_ws_ columns
        ws_fmi_cols_from_env = [f"ws_{sid}" for sid in fmisids_from_ws_env_list]
        eu_ws_cols_from_df = [col for col in df.columns if col.startswith("eu_ws_")]
        
        candidate_ws_cols = sorted(list(set(ws_fmi_cols_from_env + eu_ws_cols_from_df)))
        ws_cols_to_use = [col for col in candidate_ws_cols if col in df.columns]
        
        logger.info(f"Wind Power Model Training: FMISID_WS is set. Using FMI WS stations: {fmisids_from_ws_env_list}.")
        logger.info(f"Wind Power Model Training: Resulting ws_cols (FMI-specific from FMISID_WS and all eu_ws_): {ws_cols_to_use}")

        if not ws_cols_to_use and fmisids_from_ws_env_list: # If FMISID_WS was specified but yielded no columns
            raise KeyError(f"[ERROR] Wind Power Model: FMISID_WS was set to '{fmisid_ws_str}', but no corresponding ws_ or eu_ws_ columns were found in the DataFrame. Available ws/eu_ws columns in df: {all_df_ws_cols}")
    else:
        logger.info("Wind Power Model Training: FMISID_WS is not set. Using all available ws_ and eu_ws_ prefixed columns from DataFrame.")
        ws_cols_to_use = all_df_ws_cols # Fallback to all ws/eu_ws columns from df

    # Select t_cols: Only from FMI stations common to FMISID_WS and FMISID_T
    # This logic applies only if FMISID_WS was set (meaning fmisids_from_ws_env_list is populated)
    t_cols_to_use = []
    if fmisids_from_ws_env_list: # FMISID_WS was set and processed
        if fmisid_t_str:
            fmisids_from_t_env_set = {sid.strip() for sid in fmisid_t_str.split(',') if sid.strip()}
            common_fmisids = [sid for sid in fmisids_from_ws_env_list if sid in fmisids_from_t_env_set]
            
            if common_fmisids:
                t_cols_for_common_stations = [f"t_{sid}" for sid in common_fmisids]
                t_cols_to_use = [col for col in t_cols_for_common_stations if col in df.columns]
                logger.info(f"Wind Power Model Training: FMISID_T is set. Using temperature data from common FMI stations (present in both FMISID_WS and FMISID_T): {common_fmisids}. Resulting t_cols: {t_cols_to_use}")
            else:
                logger.info("Wind Power Model Training: FMISID_T is set, but no common FMI stations found between FMISID_WS and FMISID_T. No FMI t_ features from this logic will be used for the wind model.")
        else: # FMISID_WS is set, but FMISID_T is not
            logger.info("Wind Power Model Training: FMISID_WS is set, but FMISID_T is not. No FMI t_ features from FMISID_T will be used for the wind model based on intersection.")
        # t_cols_to_use remains empty if no common stations or FMISID_T not set
    else: # FMISID_WS was NOT set (fallback case for ws_cols)
        logger.info("Wind Power Model Training: FMISID_WS was not set. Falling back to using all available t_ prefixed columns from DataFrame for temperature features.")
        t_cols_to_use = all_df_t_cols # Fallback to all t_ columns from df
    # --- MODIFICATION END ---

    # Calculate derived wind features using the selected ws_cols_to_use
    if ws_cols_to_use:
        df['Avg_WindSpeed'] = df[ws_cols_to_use].mean(axis=1)
        df['WindSpeed_Variance'] = df[ws_cols_to_use].var(axis=1)
    else:
        # This case should ideally be rare if data is present, or caught if FMISID_WS was misconfigured.
        # If ws_cols_to_use is empty (e.g., FMISID_WS not set AND no ws_/eu_ws_ cols in df by default)
        logger.warning("Wind Power Model Training: ws_cols_to_use is empty. Avg_WindSpeed and WindSpeed_Variance will be NaN. This might be due to FMISID_WS not being set and no ws_/eu_ws_ columns in data, or FMISID_WS not matching any available columns.")
        df['Avg_WindSpeed'] = pd.Series(dtype='float64', index=df.index) 
        df['WindSpeed_Variance'] = pd.Series(dtype='float64', index=df.index)

    feature_columns = ws_cols_to_use + t_cols_to_use + [
        # 'hour_sin', 'hour_cos', # Keep commented
        'WindPowerCapacityMW',
        'Avg_WindSpeed',
        'WindSpeed_Variance'
    ]
    # Deduplicate and sort feature_columns for consistency
    feature_columns = sorted(list(set(feature_columns)))
    logger.info(f"Wind Power Model Training: Final feature columns: {feature_columns}")

    target_col = 'WindProductionPercent'

    missing_cols = [col for col in feature_columns if col not in df.columns]
    if missing_cols:
        raise KeyError(f"[ERROR] Missing feature columns: {missing_cols}")

    if target_col not in df.columns:
        raise KeyError(f"[ERROR] Target column '{target_col}' not found in dataframe.")

    initial_count = df.shape[0]
    df.dropna(subset=feature_columns + [target_col], inplace=True)
    dropped_count = initial_count - df.shape[0]
    if dropped_count > 0:
        logger.info(f"Dropped {dropped_count} rows with NaN values based on features: {feature_columns} and target: {target_col}.")

    if df.empty:
        logger.error("DataFrame became empty after dropping NaN values. Cannot proceed with training.")
        # Raise an error to make it explicit that training cannot happen.
        raise ValueError("No valid data remaining after NaN removal for wind power model training.")

    X = df[feature_columns]
    y = df[target_col]

    return X, y

def train_windpower_xgb(df: pd.DataFrame):
    # logger.info(f"Train model: Reading hyperparameters")

    try:
        WIND_POWER_XGB_HYPERPARAMS = os.getenv("WIND_POWER_XGB_HYPERPARAMS", "models/windpower_xgb_hyperparams.json")
        if WIND_POWER_XGB_HYPERPARAMS is None:
            raise ValueError("WIND_POWER_XGB_HYPERPARAMS is not set.")
    except ValueError as e:
        logger.error(f"Missing environment variable for XGB hyperparams.", exc_info=True)
        sys.exit(1)

    try:
        with open(WIND_POWER_XGB_HYPERPARAMS, 'r') as f:
            hyperparams = json.load(f)
    except FileNotFoundError:
        logger.error(f"Hyperparameters file not found at {WIND_POWER_XGB_HYPERPARAMS}.", exc_info=True)
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Decoding JSON: {e}", exc_info=True)
        sys.exit(1)

    # logger.info(f"Train model: Preprocessing wind power data")
    X_features, y_target = preprocess_data(df)

    # Sort the feature columns to ensure predictable order
    X_features = X_features[sorted(X_features.columns)]

    # logger.info(f"Input data shape: {X_features.shape}, Target shape: {y_target.shape}")

    train_X, test_X, train_y, test_y = train_test_split(
        X_features, 
        y_target, 
        test_size=0.1, 
        shuffle=False, 
        random_state=42
    )

    logger.info(f"Train set: {train_X.shape}, Test set: {test_X.shape}")
    
    # Print final training columns, sanity check
    logger.info(f"WS model features: {', '.join(X_features.columns)}")
    
    # Print tail of the training data
    logger.info(f"Training with Fingrid wind power data up to {df['timestamp'].max()}, with tail:")
    print(X_features.tail())
    
    # Train the model
    logger.info(f"XGBoost for wind power: ")
    logger.info(f", ".join(f"{k}={v}" for k, v in hyperparams.items()))

    # First, create a model with early stopping to find the optimal number of trees
    logger.info(f"Fitting model with early stopping...")
    early_stopping_model = xgb.XGBRegressor(**hyperparams)
    early_stopping_model.fit(train_X, train_y, eval_set=[(test_X, test_y)], verbose=500)

    # Get the best iteration from early stopping
    best_iteration = early_stopping_model.best_iteration
    logger.info(f"Best iteration from early stopping: {best_iteration}")

    # Create a copy of hyperparams without early_stopping_rounds for the final fit
    training_params = {k: v for k, v in hyperparams.items() if k not in ["test_size", "early_stopping_rounds"]}

    # Set the optimal number of trees and refit on all data without early stopping
    final_model = xgb.XGBRegressor(**training_params)
    final_model.set_params(n_estimators=best_iteration)
    logger.info(f"Refitting model on all data with optimal n_estimators={best_iteration}...")
    final_model.fit(X_features, y_target, verbose=500)

    # Use the final model (trained on all data) for further evaluation
    xgb_model = final_model

    logger.info(f"Wind power model training complete.")
    return xgb_model
