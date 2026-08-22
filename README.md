# ISRU Site-Selection-Engine

Status: In Development

The ISRU Site-Selection Engine takes the NASA LOLA data for the Moon's south pole and
identifies candidate base locations from their proximity to cold traps and to well lit power
areas.

The two resources pull in opposite directions. Permanently shadowed regions (PSRs) hold the
volatiles worth mining, but they are cold and dark, while peaks of eternal light (PELs) offer
the illumination needed to power a base. A viable site has to sit close to both. The engine
derives both region classes from the illumination data, characterises them against elevation
and slope, and measures the distance from every point on the map to each class.

The pipeline currently produces the region tables and distance maps described below. The
scoring step that combines them into a ranked site list is not yet implemented — see
[Roadmap](#roadmap).

---

## How It Works

The pipeline in `src/Main.py` runs the following steps.

1. **Load rasters.** The illumination and altitude GeoTIFFs are read with `rasterio`.
2. **Resample to a common grid.** The 10 m/px altitude raster is reprojected onto the
   60 m/px illumination grid using average resampling, so that every layer shares one
   geometry. All later steps work in that 60 m grid.
3. **Convert altitude to elevation.** LOLA altitudes are radii from the Moon's centre, so the
   1,737,400 m reference sphere radius is subtracted to give elevation relative to that
   sphere.
4. **Scale illumination.** The raw illumination band is multiplied by its raster scale factor
   and converted to a percentage of time each pixel is sunlit.
5. **Derive slope.** The elevation gradient is taken in both axes using the true pixel
   spacing; slope is the arctangent of the gradient magnitude, in degrees.
6. **Label regions.** Illumination is thresholded into PSRs and PELs, and each contiguous
   patch is labelled using 8-connectivity, so that diagonal neighbours count as connected.
7. **Measure regions.** Each labelled region gets a pixel count and a row in a table holding
   its mean illumination, elevation, and slope.
8. **Filter.** Regions below a minimum pixel count are separated out, so that single-pixel
   noise does not reach the analysis. Both the kept and the omitted rows are returned.
9. **Map distances.** A Euclidean distance transform gives, for every pixel, the distance in
   metres to the nearest PSR and to the nearest PEL. Pixels inside a region are `NaN`.

### Tunable Parameters

| Parameter               | Location                                 | Current value | Meaning                                                                        |
| ----------------------- | ---------------------------------------- | ------------- | ------------------------------------------------------------------------------ |
| `PSR_THRESHOLD`         | `src/Main.py`                            | `0`           | A pixel is part of a PSR at or below this illumination percentage.             |
| `PEL_THRESHOLD`         | `src/Main.py`                            | `55`          | A pixel is part of a PEL at or above this illumination percentage.             |
| `PIXEL_SIZE`            | `src/Main.py`                            | `60`          | The size of each pixel in terms of m²                                          |
| `REGION_SIZE_THRESHOLD` | `src/Main.py`, `filter_region_data` call | `10`          | Regions of 10 pixels or fewer are omitted. At 60 m²/px, one pixel is 3,600 m². |
| `ALTITUDE_OFFSET`       | `src/FileProccesing.py`                  | `1737400`     | LOLA reference sphere radius, in metres.                                       |

---

## Project Structure

```
.
├── data/                 # Rasters and QGIS project (untracked — see Data)
├── src/
│   ├── Main.py           # Pipeline wiring, file paths, and thresholds
│   ├── FileProccesing.py # Raster I/O, resampling, unit conversion, slope, plotting
│   └── Regions.py        # Thresholding, labelling, region statistics, distances, filtering
├── Requirements.txt
└── README.md
```

`FileProccesing.py` and `Regions.py` each carry a `__main__` block with small worked examples,
which is the quickest way to see what an individual function returns.

---

## Setup

Built against Python 3.13.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r Requirements.txt
```

Note the capital `R` in `Requirements.txt`. The file is a full freeze of the environment; the
direct dependencies are `rasterio`, `numpy`, `scipy`, `pandas`, and `matplotlib`.

---

## Data

The rasters are large and are not tracked in this repository. `data/` is gitignored, so a
fresh clone has no inputs and the pipeline will not run until they are put in place.

### Sources

1. [LOLA Illumination (ABGVIS_85S_060M_201608)](https://pgda.gsfc.nasa.gov/products/69) —
   average sun visibility of each 60 m × 60 m pixel, from 85°S to the south pole.
2. [LOLA DEM (LDEM_85S_10M_FLOAT)](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/float_img/) —
   altitude of each 10 m × 10 m pixel, from 85°S to the south pole.

### Preparation

The DEM needs a conversion step before the pipeline can use it. LOLA distributes its values in
kilometres while the pixel spacing is in metres, and slope is meaningless until the two agree.

1. Download both products.
2. Open the DEM in QGIS and convert its values from kilometres to metres. `data/Moon.qgz` is
   the QGIS project used for this.
3. Export the result as a GeoTIFF.
4. Place the files in `data/` under the exact names the pipeline expects:
   - `data/Altitude-rasterize.tif`
   - `data/SunVisibility(abgvis_85S_060M_201608).tiff`

The exported altitudes are still radii measured from the Moon's centre. Step 3 of the pipeline
converts them to elevations relative to the 1,737.4 km reference sphere — the perfectly smooth
average radius of the Moon used as the standard datum.

---

## Usage

```bash
python src/Main.py
```

Run this from the repository root. `Main.py` refers to its inputs as `data/...` relative to the
working directory, so running it from inside `src/` will fail to find the rasters.

The run prints the PSR and PEL region tables along with the rows omitted by the size filter.
Layer plotting is available through `plot_layers` in `FileProccesing.py`; the call in `Main.py`
is currently commented out.

---

## Roadmap

- Combine the PSR and PEL distance maps into a single site score, and rank candidate locations.
- Add slope and region-size constraints to the scoring, for landing and construction viability.
- Re-enable plotting and write figures to an `output/` directory.
