# ISRU Site-Selection-Engine

Status: In Development

The ISRU Site-Selection Engine takes the NASA LOLA data for the Moon's south pole and
identifies candidate base locations from their proximity to cold traps and to well lit power
areas.

The two resources pull in opposite directions. Permanently shadowed regions (PSRs) hold the
volatiles worth mining, but they are cold and dark, while peaks of eternal light (PELs) offer
the illumination needed to power a base. A viable site has to sit close to both. The engine
derives both region classes from the illumination data, characterises them against elevation
and slope, pairs every PSR with the PELs within walking distance of it, and scores and ranks
those pairs.

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
6. **Label regions.** Pixels that are `NaN` in any layer are masked out. Illumination is then
   thresholded into PSRs and PELs, and each contiguous patch is labelled using
   8-connectivity, so that diagonal neighbours count as connected.
7. **Measure regions.** Each labelled region gets a pixel count and a row in a table holding
   its mean illumination, elevation, and slope.
8. **Filter by size.** Regions below a minimum pixel count are separated out, so that
   single-pixel noise does not reach the analysis.
9. **Filter by slope.** Regions whose mean slope is above the slope threshold are separated
   out, since they are unsuitable for landing and construction.
10. **Pair regions.** For each PEL, a Euclidean distance transform gives the distance in metres
    from every pixel to that PEL. Every PSR whose nearest pixel is within the feasible distance
    is paired with it.
11. **Score pairs.** Each pair is scored on distance, PEL illumination, and PSR size, and the
    pairs are ranked from best to worst (see [Scoring](#scoring)).
12. **Plot.** The input layers, a score breakdown of the top 5 pairs, and a map of where those
    pairs sit are written to `output/` (see [Outputs](#outputs)).

### Scoring

Each criterion is scaled to a 0–1 score, where 1 is best:

| Score        | Calculation                                                                                         |
| ------------ | --------------------------------------------------------------------------------------------------- |
| Distance     | `1 - distance / FEASIBLE_DISTANCE`, so a pair that touches scores 1 and one at the limit scores 0.  |
| Illumination | The PEL's mean illumination, min-max scaled from `PEL_THRESHOLD` up to the brightest paired PEL.     |
| Size         | The log of the PSR's pixel count, min-max scaled across all pairs.                                  |

The total score is the weighted mean of the three, using `DISTANCE_WEIGHT`,
`ILLUMINATION_WEIGHT`, and `SIZE_WEIGHT`. The table also records what percentage of each
pair's total comes from each criterion.

Illumination and size are scaled against the other pairs in the same run, so a score compares
a pair with the other candidates and is not an absolute measure.

### Tunable Parameters

| Parameter               | Location                | Current value | Meaning                                                                                                                                                      |
| ----------------------- | ----------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `PSR_THRESHOLD`         | `src/Main.py`           | `0`           | A pixel is part of a PSR at or below this illumination percentage.                                                                                           |
| `PEL_THRESHOLD`         | `src/Main.py`           | `55`          | A pixel is part of a PEL at or above this illumination percentage.                                                                                           |
| `PIXEL_SIZE`            | `src/Main.py`           | `60`          | The side length of each pixel, in metres. One pixel covers 3,600 m².                                                                                         |
| `REGION_SIZE_THRESHOLD` | `src/Main.py`           | `10`          | Regions of 10 pixels or fewer are omitted.                                                                                                                   |
| `SLOPE_THRESHOLD`       | `src/Main.py`           | `10`          | The maximum mean slope of a region for it to be considered, in degrees.                                                                                      |
| `FEASIBLE_DISTANCE`     | `src/Main.py`           | `2000`        | The maximum PSR to PEL distance for a pair, in metres. This is the radial limit for astronauts without a rover from **[THIS PAPER](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2025JE009434)**. |
| `DISTANCE_WEIGHT`       | `src/Main.py`           | `1.0`         | The weight that distance holds in the final pair score.                                                                                                      |
| `ILLUMINATION_WEIGHT`   | `src/Main.py`           | `1.0`         | The weight that PEL illumination holds in the final pair score.                                                                                              |
| `SIZE_WEIGHT`           | `src/Main.py`           | `1.0`         | The weight that PSR size holds in the final pair score.                                                                                                      |
| `ALTITUDE_OFFSET`       | `src/FileProcessing.py` | `1737400`     | LOLA reference sphere radius, in metres.                                                                                                                     |

---

## Project Structure

```
.
├── data/                  # Rasters and QGIS project (untracked — see Data)
├── output/                # Generated plots (untracked — created on each run)
├── src/
│   ├── Main.py            # Pipeline wiring, file paths, thresholds, and weights
│   ├── FileProcessing.py  # Raster I/O, resampling, unit conversion, and slope
│   ├── Regions.py         # Validity mask, labelling, region statistics, distances, filtering
│   ├── Analysis.py        # PSR to PEL pairing and pair scoring
│   └── Display.py         # Layer plots, score chart, and pair location map
├── Requirements.txt
└── README.md
```

Every module in `src/` other than `Main.py` carries a `__main__` block with small worked
examples, which is the quickest way to see what an individual function returns.

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

Run this from the repository root. `Main.py` refers to its inputs and outputs as `data/...` and
`output/...` relative to the working directory, so running it from inside `src/` will fail to
find the rasters.

The run prints the scored pair table, ranked from best to worst, saves the plots below, and
opens them in matplotlib windows. Close the windows to let the run continue.

### Outputs

| File                          | Contents                                                                                     |
| ----------------------------- | -------------------------------------------------------------------------------------------- |
| `output/plots/*.png`          | The elevation, illumination, slope, PSR region, and PEL region layers.                       |
| `output/scored_data.png`      | A stacked bar chart of the top 5 pairs, split into the contribution of each criterion.       |
| `output/pair_locations.png`   | The top 5 pairs on the illumination map, each joined at its closest points and marked at the midpoint, coloured by total score. |

`output/` is gitignored and is created on the first run.

---

## Roadmap

- Exit cleanly when no PSR and PEL pairs fall within the feasible distance. The plotting steps
  currently fail on an empty score table.
- Make the number of pairs shown in the plots (currently 5) a parameter in `Main.py`.
