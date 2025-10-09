import pandas as pd

def check_ship_coverage():
    """
    Analyzes the model's performance on known vs. unknown ships.
    """
    try:
        # 1. Load all necessary files
        model_performance_df = pd.read_csv('model_performance_comparison.csv')
        training_df = pd.read_csv('lgbm/hpnt.csv')
        ship_info_df = pd.read_csv('ship_info.csv')
        new_ships_df = pd.read_csv('new_ships.csv')

        print("Files loaded successfully.")

        # 2. Get the set of training ship call signs
        training_call_signs = set(training_df['호출부호'])

        # 3. Create a mapping from ship name to call sign
        # Drop duplicates to ensure a one-to-one mapping where possible
        ship_info_unique = ship_info_df.drop_duplicates(subset='선명', keep='first')
        name_to_call_sign_map = pd.Series(ship_info_unique['호출부호'].values, index=ship_info_unique['선명']).to_dict()

        # 4. Map ship names in performance data to call signs
        model_performance_df['호출부호'] = model_performance_df['선명'].map(name_to_call_sign_map)

        # 5. Separate into known and unknown ships
        model_performance_df['is_known'] = model_performance_df['호출부호'].isin(training_call_signs)

        known_ships_df = model_performance_df[model_performance_df['is_known'] == True]
        unknown_ships_df = model_performance_df[model_performance_df['is_known'] == False]

        print(f"\nTotal ships in performance data: {len(model_performance_df)}")
        print(f"Number of known ships (in training data): {len(known_ships_df)}")
        print(f"Number of unknown ships (not in training data): {len(unknown_ships_df)}")

        # 6. Calculate MAE for each group
        if not known_ships_df.empty:
            mae_known = known_ships_df['절대시간차이'].mean()
            print(f"\nMAE for known ships: {mae_known:.2f} hours")
        else:
            print("No known ships found in the performance data.")

        if not unknown_ships_df.empty:
            mae_unknown = unknown_ships_df['절대시간차이'].mean()
            print(f"MAE for unknown ships: {mae_unknown:.2f} hours")
        else:
            print("No unknown ships found in the performance data.")

        # 7. Check which of the 'new_ships' are in the unknown category
        new_ship_names = set(new_ships_df['선명'])
        unknown_new_ships = new_ship_names.intersection(set(unknown_ships_df['선명']))

        print(f"\nOut of {len(new_ship_names)} ships in new_ships.csv, {len(unknown_new_ships)} were in the 'unknown' prediction set.")
        if unknown_new_ships:
            print("The following new ships were not in the training data:")
            for ship in sorted(list(unknown_new_ships)):
                print(f"- {ship}")

    except FileNotFoundError as e:
        print(f"Error: {e}. Please make sure all required CSV files are present.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    check_ship_coverage()
