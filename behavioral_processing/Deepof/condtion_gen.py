import os
import pandas as pd # Import pandas for creating the table (DataFrame)

# --- Configuration ---
project_path = os.path.join("/mnt", "d", "Project", "DeepOF", "deepof_project")
tables_path = os.path.join(project_path, "Tables")

# --- Get Experiment IDs (Folder Names) from Tables Directory ---
experiment_ids = []
print(f"Looking for experiment IDs (folder names) in: {tables_path}")
if not os.path.isdir(tables_path):
    print(f"ERROR: Tables directory not found at {tables_path}. Cannot proceed.")
    # Consider exiting or handling the error appropriately
    # exit()
else:
    try:
        for entry in os.listdir(tables_path):
            full_entry_path = os.path.join(tables_path, entry)
            if os.path.isdir(full_entry_path):
                experiment_ids.append(entry) # Add folder name as an experiment ID
        print(f"Found {len(experiment_ids)} potential experiment IDs (folders) in Tables directory.")
        if not experiment_ids:
             print(f"Warning: No subdirectories (experiment IDs) found in {tables_path}.")
    except Exception as e:
        print(f"ERROR: Failed to read Tables directory {tables_path}: {e}")
        experiment_ids = [] # Ensure list is empty on error

# --- Categorize Experiment IDs based on keywords ---
results_list = []

if experiment_ids:
    print("\nCategorizing experiment IDs...")
    for exp_id in sorted(experiment_ids): # Sort for consistent order
        record = {'experiment_id': exp_id} # Keep experiment_id as the first key for now
        exp_id_lower = exp_id.lower() # Use lowercase for case-insensitive matching

        isHOM = 'n-HOM'
        isWT = 'n-wt'
        assigned_genotype = 'unknown' # Default if no keyword matches

        # Determine genotype and flags based on keywords
        if 'het' in exp_id_lower:
            assigned_genotype = 'het'
        elif 'hom' in exp_id_lower:
            assigned_genotype = 'HOM'
            isHOM = 'HOM'
        elif 'wt' in exp_id_lower or '-con-' in exp_id_lower:
            assigned_genotype = 'wt'
            isWT = 'wt'

        # Assign values to the record dictionary
        record['SS2'] = assigned_genotype
        record['SS2binH'] = isHOM
        record['SS2binW'] = isWT

        results_list.append(record)

    # --- Create DataFrame ---
    if results_list:
        results_df = pd.DataFrame(results_list)

        if not results_df.empty: # Proceed only if the DataFrame is not empty
            n_rows = len(results_df)
            # Generate the values for the new column
            # Rows are 0, 1, 2,... up to n_rows
            new_column_values = [] # Initialize with empty string for the first row
            if n_rows > 1:
                 numbers_for_other_rows = list(range(n_rows))
                 new_column_values.extend(numbers_for_other_rows)

            # Insert the new column at the beginning (index 0) with no name
            results_df.insert(0, '', new_column_values)

        output_csv_path = os.path.join(project_path, "conditions.csv")
        try:
            results_df.to_csv(output_csv_path, index=False)
            print(f"\nResults table saved to: {output_csv_path}")

        except Exception as e:
            print(f"\nERROR: Failed to save results table to CSV: {e}")

    else:
        # This case should ideally not be reached if experiment_ids was not empty,
        # but included for completeness.
        print("\nNo categorization results generated (results_list is empty).")

else:
    print("\nNo experiment IDs found to categorize.")

print("\nScript finished.")
