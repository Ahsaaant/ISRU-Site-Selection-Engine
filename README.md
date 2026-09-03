# ISRU Site-Selection Engine

Status: Phases 0-4 complete

The ISRU Site-Selection Engine takes the NASA LOLA data for the Moon's south pole and
identifies candidate base locations from their proximity to cold traps and to well lit power
areas.

The two resources pull in opposite directions. Permanently shadowed regions (PSRs) hold the
volatiles worth mining, but they are cold and dark, while peaks of eternal light (PELs) offer
the illumination needed to power a base. A viable site has to sit close to both. The engine
derives both region classes from the illumination data, characterises them against elevation
and slope, measures the distance between every viable pair, and ranks the survivors under a
weighted score.

**The headline result is scarcity.** Of 5,303 cold traps larger than 10 pixels, only 63 have
any peak of eternal light within the 2 km crew walkback limit — 1.2%. The median cold trap sits
28.9 km from the nearest one. Applying the viability constraints leaves **ten candidate sites**,
drawn from five distinct cold traps. The full analysis is in [`docs/WRITEUP.md`](docs/WRITEUP.md).

---

## How It Works

The pipeline in `src/Main.py` runs the following steps.

1. **Load rasters.** The illumination and altitude GeoTIFFs are read with `rasterio`, and each
   derived layer's value range is printed as a plausibility check on load.
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
8. **Filter speckle.** Regions below a minimum pixel count are separated out, so that
   single-pixel noise does not reach the analysis.
9. **Apply hard constraints.** A PEL too steep to build on and a PSR too small to be worth
   mining are removed outright, before scoring, so that a disqualified region cannot be
   carried up the ranking by a strong showing on another factor.
10. **Pair.** For each surviving PEL, a Euclidean distance transform inside its bounding box
    gives the edge-to-edge distance to every nearby PSR. Pairs within the feasible distance
    become rows in a long-format table of `(PEL, PSR, distance)` triples.
11. **Score and rank.** Each factor is rescaled to 0-1, inverted where lower is better, and
    combined under tunable weights. The whole pairing and scoring runs at three distance
    tiers.
12. **Test the weights.** 2,000 random weightings are drawn to measure whether the ranking
    survives them, alongside four corner weightings with each factor dominant in turn.
13. **Validate.** Six catalogued craters are located in the derived PSR mask, the slope layer
    is checked against Horn's method, and the pairing table is checked for the failure modes
    that would make it silently wrong.
14. **Write outputs.** Tables, figures and a run summary go to `output/`.

### Tunable Parameters

| Parameter               | Location             | Current value | Meaning                                                                                    |
| ----------------------- | -------------------- | ------------- | ------------------------------------------------------------------------------------------ |
| `PSR_THRESHOLD`         | `src/Main.py`        | `0`           | A pixel is part of a PSR at or below this illumination percentage.                          |
| `PEL_THRESHOLD`         | `src/Main.py`        | `55`          | A pixel is part of a PEL above this illumination percentage.                                |
| `REGION_SIZE_THRESHOLD` | `src/Main.py`        | `10`          | Regions of this many pixels or fewer are speckle and are dropped. One pixel is 3,600 m².    |
| `MAX_PEL_SLOPE`         | `src/Main.py`        | `15`          | Hard constraint. A PEL whose mean slope exceeds this, in degrees, is disqualified.          |
| `MIN_PSR_AREA`          | `src/Main.py`        | `1.0`         | Hard constraint. A PSR smaller than this, in km², is disqualified.                          |
| `PIXEL_SIZE`            | `src/Main.py`        | `60`          | The edge length of each pixel, in metres.                                                   |
| `FEASIBLE_DISTANCE`     | `src/Main.py`        | `2000`        | Crew walkback limit in metres, from [this paper](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2025JE009434). |
| `DISTANCE_TIERS`        | `src/Main.py`        | 2/5/10 km     | The three mission architectures the analysis is run under.                                  |
| `DEFAULT_WEIGHTS`       | `src/Analysis.py`    | see below     | Scoring weights: distance 0.35, illumination 0.30, PSR area 0.20, slope 0.15.               |
| `ALTITUDE_OFFSET`       | `src/FileProcessing.py` | `1737400`  | LOLA reference sphere radius, in metres.                                                    |

---

## Project Structure

```
.
├── data/                 # Rasters and QGIS project (untracked — see Data)
├── docs/
│   └── WRITEUP.md        # Method, results, validation, limitations
├── output/               # Written by a pipeline run
│   ├── figures/          # Ten PNGs: layers, masks, distance maps, pole detail, results
│   ├── tables/           # Region tables, ranked sites per tier, sensitivity, validation
│   └── summary.json      # Parameters and headline numbers from the last run
├── src/
│   ├── Main.py           # Pipeline wiring, file paths, thresholds and constraints
│   ├── FileProcessing.py # Raster I/O, resampling, unit conversion, slope, plotting
│   ├── Regions.py        # Thresholding, labelling, region statistics, distances, filtering
│   ├── Analysis.py       # Pairing, hard constraints, scoring, ranking, weight sensitivity
│   └── Validation.py     # Horn slope, crater geolocation, pairing sanity checks
├── Requirements.txt
└── README.md
```

`FileProcessing.py`, `Regions.py`, `Analysis.py` and `Validation.py` each carry a `__main__`
block with small worked examples, which is the quickest way to see what an individual function
returns. `Validation.py`'s block checks Horn's method against an analytic cone of known slope
and shows the pairing sanity check correctly failing on a deliberately broken input.

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

1. [LOLA Illumination (AVGVISIB_85S_060M_201608)](https://pgda.gsfc.nasa.gov/products/69) —
   average sun visibility of each 60 m × 60 m pixel, from 85°S to the south pole.
2. [LOLA DEM (LDEM_85S_10M_FLOAT)](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/float_img/) —
   altitude of each 10 m × 10 m pixel, from 85°S to the south pole.

Use the PGDA **GeoTIFF** for illumination, not the raw PDS `.IMG`. The raw `.LBL` carries
`CENTER_LATITUDE = 90` on a south polar product; GDAL believes it and builds a north polar CRS.

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
working directory, so running it from inside `src/` will fail to find the rasters. A full run
takes well under a minute and overwrites everything in `output/`.

---

## Results

The ranked sites, at the 2 km walkback tier:

| Rank | Pair                  | Distance | PEL illumination | PEL slope | PSR area  | Score |
| ---- | --------------------- | -------- | ---------------- | --------- | --------- | ----- |
| 1    | PSR 24969 – PEL 852   | 1,195 m  | 59.2%            | 4.0°      | 234.4 km² | 0.68  |
| 2    | PSR 24969 – PEL 985   | 1,655 m  | 64.2%            | 3.4°      | 234.4 km² | 0.65  |
| 3    | PSR 24969 – PEL 1001  | 1,697 m  | 64.4%            | 3.1°      | 234.4 km² | 0.64  |
| 4    | PSR 25131 – PEL 808   | 1,342 m  | 64.9%            | 5.6°      | 1.9 km²   | 0.59  |
| 5    | PSR 27173 – PEL 897   | 1,380 m  | 62.1%            | 3.2°      | 1.1 km²   | 0.52  |

PSR 24969 is the Shackleton complex, 234 km² of shadow beginning 2 km from the pole. Its
pairings hold the top three places under 85-87% of 2,000 random weightings, and three of the
four corner weightings also place it first. That the textbook site tops the ranking, without
being told to, is the strongest validation the project has.

Relaxing the distance assumption widens the field considerably: 77 sites at 5 km, 246 at 10 km.

---

## Validation

| Check                                    | Result                                                         |
| ---------------------------------------- | -------------------------------------------------------------- |
| Catalogued cold traps located in the mask | 6 / 6 — Shackleton, de Gerlache, Shoemaker, Haworth, Faustini, Sverdrup |
| Longitude convention control              | Mirrored, only 1 / 6 lands on a PSR                            |
| Slope vs Horn's method (GDAL/QGIS)        | correlation 0.9983, mean absolute difference 0.257°            |
| Horn's method vs analytic cone            | 5.710° against a true 5.711°                                   |
| Pairing sanity checks                     | All pass; check confirmed to fail on a broken input            |
| Derived PSR extent                        | 9,880 km², 10.74% of the mapped area                           |

Not yet done: comparison against the published LOLA LPSR product, which is not held locally.

---

## Known Limitations

60 m resolution caps the analysis, and boulder-scale hazards are not in this data at all.
Permanent shadow indicates where ice *can* survive, not that ice is present — that needs LEND
hydrogen and Diviner temperature data. Slope is undirected, so a crater rim and a conical peak
of equal steepness are indistinguishable. Distances are straight-line and ignore terrain, so
real traverse cost is higher, which matters most given the 2 km threshold models crew walkback.
Illumination is ground-level and time-averaged over a lunar precession cycle. Scores are
comparative within this candidate set only.
