# NPS-Open-Climate-Data

Code used to generate open data for historical climate variables across all US National Parks.

## Python Package `nps_climate_data`

This repository contains a Python package to fetch climate data (DAYMET, ERA5) for US National Parks using Google Earth Engine.

### Installation

```bash
pip install -e .
```

### Usage

```python
import nps_climate_data as nps
import ee

# Authenticate/Initialize Earth Engine
try:
    ee.Initialize()
except:
    ee.Authenticate()
    ee.Initialize()

# Fetch data for a park
df = nps.get_data(
    park_name="Yosemite National Park",
    start_date="2020-01-01",
    end_date="2021-01-01",
    output_file="yosemite_climate.csv"
)

print(df.head())
```

## TODO / Future Improvements

- [ ] **Add Datasets**: Incorporate additional climate datasets (e.g., GRIDMET, PRISM) to broaden the scope.
- [ ] **Preprocessing**: Add derived variables, such as calculating wind speed/direction from u and v components.
- [ ] **Multipart Parks**: Better handling for parks with disjoint geometries. Currently, they are unioned into a single geometry for reduction. Consider separating them (e.g., "Park Unit A", "Park Unit B").
- [ ] **Flexible Naming**: Implement fuzzy matching or a suggestion system ("Did you mean...?") for park names to improve user experience.
- [ ] **CLI**: Add a Command Line Interface for non-python usage (e.g. `nps-climate get "Acadia" ...`).
- [ ] **Large Exports**: Add support for `Export.table.toDrive` for very large queries that exceed interactive memory limits.
