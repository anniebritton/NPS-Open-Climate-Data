import ee

def get_park_boundary(park_name):
    """
    Retrieves the geometry of a National Park from the PAD-US database.
    
    Args:
        park_name (str): Exact name of the park (e.g., 'Yellowstone National Park').
        
    Returns:
        ee.FeatureCollection: Filtered collection containing the park boundary.
    """
    aoi = ee.FeatureCollection("USGS/GAP/PAD-US/v20/proclamation") \
        .filter(ee.Filter.eq('Loc_Ds', 'National Park')) \
        .filter(ee.Filter.eq('Unit_Nm', park_name))
    
    return aoi
