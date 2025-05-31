import shap
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from statsmodels.stats.stattools import durbin_watson
from statsmodels.tsa.stattools import acf
from rich import print
from xgboost import XGBRegressor
import pytz
from .logger import logger

def train_model(df, fmisid_ws, fmisid_t):
    if df.empty:
        logger.error("Input DataFrame to train_model is empty. Skipping price model training.")
        return None

    # Ensure the target variable 'Price_cpkWh' exists and drop rows where it's NaN
    if 'Price_cpkWh' not in df.columns:
        logger.error("'Price_cpkWh' column is missing from the DataFrame. Skipping price model training.")
        return None
    
    df = df.dropna(subset=['Price_cpkWh'])
    if df.empty:
        logger.error("DataFrame is empty after dropping rows with NaN Price_cpkWh. Skipping price model training.")
        return None
        
    logger.info(f"Starting price model training with {len(df)} rows after initial NaN drop.")
    
    # Drop the target column from training data
    if 'PricePredict_cpkWh' in df.columns:
        df = df.drop(columns=['PricePredict_cpkWh'])

    # Process timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['day_of_week'] = df['timestamp'].dt.dayofweek + 1
    df['hour'] = df['timestamp'].dt.hour
    df['year'] = df['timestamp'].dt.year

    # Cap extreme outliers based on percentiles and filter the DataFrame
    upper_limit = df['Price_cpkWh'].quantile(0.9995)
    lower_limit = df['Price_cpkWh'].quantile(0.0008)
    df['Price_cpkWh'] = np.clip(df['Price_cpkWh'], lower_limit, upper_limit)

    # Preprocess cyclical time-based features
    df['day_of_week_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
    df['day_of_week_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)

    # Calculate temp_mean and temp_variance using provided fmisid_t columns
    # Ensure fmisid_t contains columns that actually exist in df and have some data
    valid_fmisid_t = [col for col in fmisid_t if col in df.columns and df[col].notna().any()]
    if valid_fmisid_t:
        df['temp_mean'] = df[valid_fmisid_t].mean(axis=1)
        df['temp_variance'] = df[valid_fmisid_t].var(axis=1)
    else:
        df['temp_mean'] = pd.NA # Or np.nan, consistent with how missing data is handled
        df['temp_variance'] = pd.NA

    # Ensure fmisid_ws contains columns that actually exist in df
    valid_fmisid_ws = [col for col in fmisid_ws if col in df.columns and df[col].notna().any()]

    # Feature selection
    _feature_columns_initial = [ # Temporary name for the list that might contain duplicates
        'year', 'day_of_week_sin', 'day_of_week_cos', 'hour_sin', 'hour_cos', 
        'NuclearPowerMW', 'ImportCapacityMW', 'WindPowerMW', 
        'temp_mean', 'temp_variance', 'holiday', 
        'sum_irradiance', 'mean_irradiance', 'std_irradiance', 'min_irradiance', 'max_irradiance',
        'SE1_FI', 'SE3_FI', 'EE_FI',
        'eu_ws_EE01', 'eu_ws_EE02', 'eu_ws_DK01', 'eu_ws_DK02', 'eu_ws_DE01', 'eu_ws_DE02', 'eu_ws_SE01', 'eu_ws_SE02', 'eu_ws_SE03',
        # 'volatile_likelihood' # This is added later in the main script if used
    ] + valid_fmisid_t + valid_fmisid_ws

    # Deduplicate _feature_columns_initial while preserving order of first appearance
    seen_columns = set()
    feature_columns = [] # This will be the final, deduplicated list
    for col_name in _feature_columns_initial:
        if col_name not in seen_columns:
            feature_columns.append(col_name)
            seen_columns.add(col_name)
    
    # Ensure all selected feature columns exist in df, drop if not (e.g. temp_mean/var if no valid_fmisid_t)
    # Use the unique, ordered list of feature column names (now named 'feature_columns')
    X_filtered = df[[col for col in feature_columns if col in df.columns]].copy()
    
    # If temp_mean or temp_variance were not created (because valid_fmisid_t was empty),
    # they might be missing from X_filtered. XGBoost can handle NaNs if they are present.
    # If they are entirely missing as columns and were expected, this could be an issue,
    # but the current setup should ensure they are present (possibly as all NaNs).

    # Target variable
    y_filtered = df['Price_cpkWh']
  
    # Split the data
    X_train, X_test, y_train, y_test = train_test_split(
        X_filtered, 
        y_filtered, 
        test_size=0.10,
        random_state=42,
        shuffle=True
    )
  
    logger.info(f"Training data shape: {X_train.shape}, sample:")
    print(X_train.sample(10, random_state=42))

    # Print feature columns used in training
    logger.info(f"Pricing model feature columns:")
    logger.info(f", ".join(X_train.columns))

    # See train_xgb.txt for history of hyperparameter tuning
    # Last update: 2025-01-19
    params = {
        'early_stopping_rounds': 50,
        'objective': 'reg:squarederror',
        'eval_metric': 'rmse',
        'n_estimators': 11655,
        'max_depth': 6,
        'learning_rate': 0.012158906047644169,
        'subsample': 0.6717186457667352,
        'colsample_bytree': 0.5938032371628845,
        'gamma': 0.02297259369577767,
        'reg_alpha': 1.4624622196040324,
        'reg_lambda': 0.09870580997491653,
        'random_state': 42,
    }

    # Train the model
    logger.info(f"XGBoost for price prediction: ")
    logger.info(f", ".join(f"{k}={v}" for k, v in params.items()))

    # First, create a model with early stopping to find the optimal number of trees
    logger.info(f"Fitting model with early stopping...")
    early_stopping_model = XGBRegressor(**params)
    early_stopping_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=500)
    
    # Get the best iteration from early stopping
    best_iteration = early_stopping_model.best_iteration
    logger.info(f"Best iteration from early stopping: {best_iteration}")
    
    # Create a copy of params without early_stopping_rounds for the final fit
    training_params = {k: v for k, v in params.items() if k != 'early_stopping_rounds'}
    
    # Set the optimal number of trees and refit on all data without early stopping
    final_model = XGBRegressor(**training_params)
    final_model.set_params(n_estimators=best_iteration)
    logger.info(f"Refitting model on all data with optimal n_estimators={best_iteration}...")
    final_model.fit(X_filtered, y_filtered, verbose=500)
    
    # Use the final model (trained on all data) for further evaluation
    xgb_model = final_model

    # SHAP analysis
    # logger.info(f"SHAP feature importances (Mean Absolute SHAP Values per Feature):")
    # explainer = shap.TreeExplainer(xgb_model)
    # shap_values = explainer.shap_values(X_test, check_additivity=False)

    # # Aggregate mean absolute SHAP values per feature for console display
    # shap_summary = np.abs(shap_values).mean(axis=0)
    # shap_summary_df = pd.DataFrame({
    #     'Feature': X_test.columns,
    #     'Mean |SHAP Value|': shap_summary
    # }).sort_values(by='Mean |SHAP Value|', ascending=False)

    # logger.info(shap_summary_df.to_string(index=False))

    # Residual analysis
    y_pred_filtered = xgb_model.predict(X_test)
    residuals = y_test - y_pred_filtered
    
    # Durbin-Watson test for autocorrelation
    dw_stat = durbin_watson(residuals)
    logger.info(f"Durbin-Watson autocorrelation test: {dw_stat:.2f}")
    
    # Autocorrelation Function for the first 5 lags
    acf_values = acf(residuals, nlags=5, fft=False)
    logger.info(f"ACF values for the first 5 lags:")
    for lag, value in enumerate(acf_values, start=1):
        logger.info(f"  Lag {lag}: {value:.4f}")
    
    # Calculate metrics
    mae = mean_absolute_error(y_test, y_pred_filtered)
    mse = mean_squared_error(y_test, y_pred_filtered)
    r2 = r2_score(y_test, y_pred_filtered)

    # Initialize lists to store metrics for random sampling (sanity check)
    mae_list, mse_list, r2_list = [], [], []

    # Perform random sampling and evaluation 10 times
    for _ in range(10):
        random_sample = df.sample(n=500, random_state=None) # Sample from the original df passed to train_model
        
        # Compute cyclical features for the sample
        random_sample['day_of_week_sin'] = np.sin(2 * np.pi * random_sample['day_of_week'] / 7)
        random_sample['day_of_week_cos'] = np.cos(2 * np.pi * random_sample['day_of_week'] / 7)
        random_sample['hour_sin'] = np.sin(2 * np.pi * random_sample['hour'] / 24)
        random_sample['hour_cos'] = np.cos(2 * np.pi * random_sample['hour'] / 24)

        # Compute temp_mean and temp_variance for the sample, using the same valid FMI columns
        if valid_fmisid_t:
            random_sample['temp_mean'] = random_sample[valid_fmisid_t].mean(axis=1)
            random_sample['temp_variance'] = random_sample[valid_fmisid_t].var(axis=1)
        else:
            random_sample['temp_mean'] = pd.NA
            random_sample['temp_variance'] = pd.NA
        
        # Match the feature selection used for training, ensuring columns exist in random_sample
        X_random_sample = random_sample[[col for col in feature_columns if col in random_sample.columns]].copy()
        
        y_random_sample_true = random_sample['Price_cpkWh']
        y_random_sample_pred = xgb_model.predict(X_random_sample)
        
        mae_list.append(mean_absolute_error(y_random_sample_true, y_random_sample_pred))
        mse_list.append(mean_squared_error(y_random_sample_true, y_random_sample_pred))
        r2_list.append(r2_score(y_random_sample_true, y_random_sample_pred))
        
    # Calculate mean of evaluation metrics
    samples_mae = np.mean(mae_list)
    samples_mse = np.mean(mse_list)
    samples_r2 = np.mean(r2_list)

    logger.info(f"Training results:\n  MAE (vs test set): {mae}\n  MSE (vs test set): {mse}\n  R² (vs test set): {r2}"
          f"\n  MAE (vs 10x500 randoms): {samples_mae}\n  MSE (vs 10x500 randoms): {samples_mse}\n  R² (vs 10x500 randoms): {samples_r2}")

    return xgb_model
