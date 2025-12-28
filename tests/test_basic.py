import sys
import os
import ee

# Add current directory to path so we can import the package in-place
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import nps_climate_data as nps

def test_basic_query():
    print("Initializing Earth Engine...")
    try:
        ee.Initialize()
    except Exception as e:
        print(f"EE Initialization failed: {e}")
        print("Please authenticate using `earthengine authenticate`.")
        return

    park_name = "Acadia National Park"
    start_date = "2020-01-01"
    end_date = "2020-01-05" # Short range for testing
    output_file = "test_acadia.csv"
    
    # Cleanup previous run
    if os.path.exists(output_file):
        os.remove(output_file)

    print(f"Running query for {park_name}...")
    try:
        df = nps.get_data(park_name, start_date, end_date, output_file=output_file)
        
        print("\nResult DataFrame Head:")
        print(df.head())
        
        if os.path.exists(output_file):
            print(f"\nSUCCESS: Output file {output_file} created.")
        else:
            print("\nFAILURE: Output file not created.")
            
    except Exception as e:
        print(f"\nERROR running query: {e}")

if __name__ == "__main__":
    test_basic_query()
