//WHAT OTHER BANDS TO INCLUDE? DITCH MODIS AND JUST DO ERA?
// UNIT ADJUSTMENTS?
// Separate multipart parks

var startDate = ee.Date('2020-01-01');
var endDate = ee.Date('2021-01-01');

function adjustModisLST(img) {
  var lstBands = ['LST_Day_1km', 'LST_Night_1km'];
  var adjusted = img.select(lstBands).multiply(0.02)
    .subtract(273.15)
    .multiply(9).divide(5).add(32);
  var otherBands = img.select(img.bandNames().removeAll(lstBands));
  return otherBands.addBands(adjusted).copyProperties(img, img.propertyNames());
}

var modisDataset = {
  name: 'MODIS',
  ic: ee.ImageCollection("MODIS/061/MOD11A1")
    .filterDate(startDate, endDate)
    .select(['LST_Day_1km', 'LST_Night_1km'])
    .map(adjustModisLST),
  scale: 1000
};

// 1. Load AOIs
var AOI = ee.FeatureCollection("USGS/GAP/PAD-US/v20/proclamation")
  .filter(ee.Filter.eq('Loc_Ds', 'National Park'));

var datasets = [
  modisDataset,
  {
    name: 'DAYMET',
    ic: ee.ImageCollection("NASA/ORNL/DAYMET_V4")
      .filterDate(startDate, endDate)
      .select(['prcp', 'srad', 'swe', 'tmax', 'tmin', 'vp']),
    scale: 1000
  },
  {
    name: 'ERA5',
    ic: ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
      .filterDate(startDate, endDate)
      .select([
        'v_component_of_wind_10m',
        'u_component_of_wind_10m',
        'snowmelt_sum',
        'snowfall_sum',
        'snow_cover',
        'snow_density',
        'snow_depth',
        'leaf_area_index_high_vegetation',
        'leaf_area_index_low_vegetation'
      ]),
    scale: 11132
  }
];

// 3. Rename bands with dataset prefix
function renameWithPrefix(img, dataset) {
  var oldNames = img.bandNames();
  var newNames = oldNames.map(function(band) {
    return ee.String(dataset.name).cat('_').cat(band);
  });
  return img.rename(newNames);
}

// 4. Prepare merged ImageCollection from all datasets
function getMergedImageCollection(datasetList) {
  var merged = ee.ImageCollection([]);
  datasetList.forEach(function(dataset) {
    var renamed = dataset.ic.map(function(img) {
      return renameWithPrefix(img, dataset);
    });
    merged = merged.merge(renamed);
  });
  return merged;
}

var mergedIC = getMergedImageCollection(datasets).aside(print);

// 5. Reduce an image over the AOI
function reduceImageOverAOI(img) {
  var dateStr = img.date().format('YYYY-MM-dd');
  return AOI.map(function(feature) {
    var regionMeans = img.reduceRegion({
      reducer: ee.Reducer.mean(),
      geometry: feature.geometry(),
      scale: 1000, // Could be adjusted per dataset if desired
      maxPixels: 1e13
    });
    return ee.Feature(feature.geometry())
      .set('Unit_Nm', feature.get('Unit_Nm'))
      .set('date', dateStr)
      .set(regionMeans);
  });
}

// 6. Map over all images and flatten result
var featuresPerImage = mergedIC.map(reduceImageOverAOI);
var flattened = featuresPerImage.flatten();

// 7. View result
print('Per-feature per-date band means:', flattened);


// Group by Unit_Nm and date, and merge band values
function mergeByUnitAndDate(fc) {
  // Convert FeatureCollection to a list
  var featureList = fc.toList(fc.size());

  // Create a dictionary where keys are 'Unit_Nm_date' and values are lists of features
  var grouped = featureList.iterate(function(feature, acc) {
    feature = ee.Feature(feature);
    var name = feature.get('Unit_Nm');
    var date = feature.get('date');
    var key = ee.String(name).cat('_').cat(date);
    acc = ee.Dictionary(acc);
    var existing = ee.List(acc.get(key, ee.List([])));
    return acc.set(key, existing.add(feature));
  }, ee.Dictionary({}));

  grouped = ee.Dictionary(grouped);

  // Map over keys to merge features
  var mergedFeatures = grouped.keys().map(function(key) {
    key = ee.String(key);
    var featureList = ee.List(grouped.get(key));

    // Use the first feature to get Unit_Nm and date
    var first = ee.Feature(featureList.get(0));
    var merged = ee.Feature(null)
      .set('Unit_Nm', first.get('Unit_Nm'))
      .set('date', first.get('date'));

    // Combine properties from all features
    var allProps = featureList.iterate(function(f, props) {
      f = ee.Feature(f);
      props = ee.Dictionary(props);
      var bandProps = f.toDictionary().remove(['Unit_Nm', 'date']);
      return props.combine(bandProps, true); // true = overwrite if needed
    }, ee.Dictionary({}));

    return merged.set(ee.Dictionary(allProps));
  });

  return ee.FeatureCollection(mergedFeatures);
}

// Apply the merge
var mergedByUnitDate = mergeByUnitAndDate(flattened);
print('Merged by Unit_Nm and date:', mergedByUnitDate);

// // List of bands
// var bandNames = [
//   'MODIS_LST_Day_1km',
//   'MODIS_LST_Night_1km',
//   'DAYMET_prcp',
//   'DAYMET_srad',
//   'DAYMET_swe',
//   'DAYMET_tmax',
//   'DAYMET_tmin',
//   'DAYMET_vp',
//   'ERA5_v_component_of_wind_10m',
//   'ERA5_u_component_of_wind_10m',
//   'ERA5_snowmelt_sum',
//   'ERA5_snowfall_sum',
//   'ERA5_snow_cover',
//   'ERA5_snow_density',
//   'ERA5_snow_depth',
//   'ERA5_leaf_area_index_high_vegetation',
//   'ERA5_leaf_area_index_low_vegetation'
// ];

// // Desired properties
// var exportProps = ['date', 'Unit_Nm'].concat(bandNames);

// var cleaned = mergedByUnitDate.map(function(feature) {
//   // Remove system:index by setting it to null
//   feature = feature.set('system:index', null);
//   // Keep only your desired properties
//   return feature.select(exportProps, null, false);
// });


Export.table.toDrive({
  collection: mergedByUnitDate,
  description: 'clean_timeseries_export',
  fileFormat: 'CSV' 
});
