import time
import pandas as pd
import os
from datetime import datetime, timedelta
from utils import get_work_plan_data, predict_work_time, run_milp_model

def run_single_process(start_date, end_date):
    """
    Runs one complete data processing cycle (crawling, prediction, optimization)
    and returns the resulting DataFrame.
    """
    print(f"HPNT data crawling for {start_date} to {end_date}...")
    try:
        work_plan_df = get_work_plan_data(start_date, end_date)
        if work_plan_df is None or work_plan_df.empty:
            print("No data was crawled. Skipping.")
            return None
        print(f"{len(work_plan_df)} crawled data found.")
    except Exception as e:
        print(f"Crawling error: {e}")
        return None

    predicted_df = predict_work_time(work_plan_df.copy())

    if 'predicted_work_time' not in predicted_df.columns:
        print("no predicted_work_time column in predicted_df. Exiting.")
        return None

    print("Optimizing with MILP model...")
    try:
        required_cols_for_milp = ['predicted_work_time', '접안예정일시', '선명', 'LOA']
        if not all(col in predicted_df.columns for col in required_cols_for_milp):
            print(f"Parameter error: missing columns ({required_cols_for_milp})")
            return None
        
        solution_df = run_milp_model(predicted_df)

        if solution_df is not None:
            start_time_ref = predicted_df['접안예정일시'].min()
            solution_df['etd_timedelta'] = pd.to_timedelta(solution_df['Completion_h'], unit='h')
            solution_df['ETD'] = start_time_ref + solution_df['etd_timedelta']
            solution_df['ETD'] = solution_df['ETD'].dt.strftime('%Y-%m-%d %H:%M')
            
            merged_df = pd.merge(solution_df, work_plan_df, left_on=['Ship', '모선항차'], right_on=['선명', '모선항차'], how='left')
            return merged_df

    except Exception as e:
        print(f"Optimization error: {e}")
    
    return None

def run_fixed_target_scenario(target_date_str, window_size):
    """
    Runs predictions daily from a 'window_size' days out towards a fixed 'target_date'
    and saves the results to a single CSV file.
    """
    try:
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d')
    except ValueError:
        print("Error: Invalid date format. Please use 'YYYY-MM-DD'.")
        return

    all_results = []

    # Loop from window_size days out up to the target date
    for i in range(window_size):
        current_call_date = target_date - timedelta(days=(window_size - 1 - i))
        call_date_str = current_call_date.strftime('%Y-%m-%d')
        
        print(f"--- Running Scenario: Call Date {call_date_str} (Data Range: {call_date_str} to {target_date_str}) ---")
        
        # Run prediction using data from the call date to the target date
        result_df = run_single_process(call_date_str, target_date_str)
        
        if result_df is not None:
            result_df['호출일'] = call_date_str
            all_results.append(result_df)

    if not all_results:
        print(f"No results processed for the {window_size}-day window.")
        return

    final_df = pd.concat(all_results, ignore_index=True)

    # Create a dedicated output folder
    output_folder = f"scenario_fixed_target/{window_size}days"
    os.makedirs(output_folder, exist_ok=True)

    # Save results to the new folder
    output_filename = f"fixed_target_etd_comparison_target_{target_date_str}_from_{window_size}days.csv"
    output_path = os.path.join(output_folder, output_filename)
    final_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    
    print(f"\nAll scenario results saved to '{output_path}'.")
    print("Top 5 rows of the saved file:")
    print(final_df.head())

if __name__ == '__main__':
    # 1. Define the date range for the entire analysis period.
    start_date_str = '2025-02-01'
    end_date_str = '2025-02-28'

    # 2. Define the different prediction windows to test.
    ANALYSIS_WINDOWS = [10, 7, 5, 3]
    
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    
    # 3. Loop through each day in the period, treating it as a target date.
    current_target_date = start_date
    while current_target_date <= end_date:
        target_date_str = current_target_date.strftime('%Y-%m-%d')
        
        # 4. For each target date, run the simulation for all defined windows.
        for window in ANALYSIS_WINDOWS:
            # Ensure the first call date is not before our analysis period starts.
            first_call_date = current_target_date - timedelta(days=(window - 1))
            if first_call_date < start_date:
                print(f"Skipping window {window} for target {target_date_str} as it starts before {start_date_str}.")
                continue

            print(f"\n{'='*20} Starting Fixed-Target Analysis for Target Date: {target_date_str} ({window}-day window) {'='*20}")
            run_fixed_target_scenario(target_date_str, window)
        
        current_target_date += timedelta(days=1)
