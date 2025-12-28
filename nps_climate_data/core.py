import ee
import pandas as pd
from .datasets import DATASETS
from .utils import get_park_boundary

def process_dataset(dataset_def, start_date, end_date):
    """
    Prepares a single dataset: filtering, selecting, renaming.
    Returns an ee.ImageCollection.
    """
    ic = ee.ImageCollection(dataset_def['asset_id']) \
        .filterDate(start_date, end_date) \
        .select(dataset_def['bands'])
    
    # Rename bands with dataset prefix
    def rename_image(img):
        # Capture pfx from closure
        pfx = dataset_def['name'] + "_"
        old_names = img.bandNames()
        new_names = old_names.map(lambda n: ee.String(pfx).cat(n))
        return img.rename(new_names)

    return ic.map(rename_image)

def get_data(park_name, start_date, end_date, output_file=None, scale=1000):
    """
    Main function to fetch climate data for a specific park.
    
    Args:
        park_name (str): Name of the park.
        start_date (str): Start date (YYYY-MM-DD).
        end_date (str): End date (YYYY-MM-DD).
        output_file (str, optional): Path to save CSV file.
        scale (int): Scale in meters for reduction. Default to 1000 matches Daymet.
        
    Returns:
        pd.DataFrame: DataFrame containing daily means for all variables.
    """
    
    # Get AOI
    aoi_fc = get_park_boundary(park_name)
    
    # Check if park exists (needs server roundtrip)
    # We do a quick check on size.
    if aoi_fc.size().getInfo() == 0:
        raise ValueError(f"Park '{park_name}' not found in PAD-US data.")
        
    # Use the union of geometries (e.g. for multipart parks)
    aoi_geom = aoi_fc.geometry()
    
    # Merge all datasets
    merged_ic = ee.ImageCollection(ee.List([]))
    
    for ds_def in DATASETS:
        ds_ic = process_dataset(ds_def, start_date, end_date)
        merged_ic = merged_ic.merge(ds_ic)
        
    def reduce_image(img):
        stats = img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=aoi_geom,
            scale=scale, 
            maxPixels=1e13,
            bestEffort=True
        )
        # Add date property
        stats = stats.set('date', img.date().format('YYYY-MM-dd'))
        return ee.Feature(None, stats)

    # Map reduction over collection
    print(f"Fetching data for {park_name} from {start_date} to {end_date}...")
    reduced_fc = merged_ic.map(reduce_image)
    
    # Execute (fetch data)
    features = reduced_fc.getInfo()['features']
    
    if not features:
        print("No data returned.")
        return pd.DataFrame()
        
    data = [f['properties'] for f in features]
    df = pd.DataFrame(data)
    
    # Post-processing: Group by date and combine columns
    # We expect 'date' column and a disjoint set of value columns per row
    if 'date' not in df.columns:
        print("Empty data received (possibly masked).")
        return df

    # Group by date and take max() (merges disjoint non-null values)
    df_final = df.groupby('date').max().reset_index()

    if output_file:
        df_final.to_csv(output_file, index=False)
        print(f"Data saved to {output_file}")
        
    return df_final
