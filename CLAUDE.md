# ISRU Site Selection Engine

Identifies candidate lunar base locations near the Moon's south pole by pairing permanently
shadowed regions (cold traps, where water ice can survive) with nearby high-illumination
terrain (viable solar power sites).

The core problem: the Moon's small axial tilt (~1.5 degrees) means crater floors near the pole
never see sunlight, while nearby rims and ridges are lit almost continuously. Ice needs
darkness; power needs light. They are mutually exclusive by location, so a viable base needs
both, close together. Site selection is therefore a proximity problem.

## Current state

Phase 0 (data acquisition and alignment): complete.
Phase 1 (derive elevation, slope, illumination, masks): complete.
Phase 2 (label regions, measure distances, create data table for each region): distances working, table not started.
Phase 3 (decide on scoring rubric, apply rubric, rank sites): not started.
Phase 4 (write-up): not started.

Rule: no phase begins until the previous one is committed and pushed.

## Structure

```
src/Main.py             orchestration; runs the pipeline
src/FileProccesing.py   raster I/O, resampling, slope, illumination scaling, plotting
src/Regions.py          region labelling and distance transforms
data/                   gitignored - rasters are hundreds of MB to GB
```

Note the existing spelling of `FileProccesing.py` — keep it consistent or rename everywhere.

## Data

Both products cover 85 degrees S to the pole. Everything is resampled onto the **60 m
illumination grid (5058 x 5058)**, which is the analysis resolution.

**Illumination** — LOLA `AVGVISIB_85S_060M_201608`, 60 m/px, from PGDA
(pgda.gsfc.nasa.gov/products/69). Values are average solar visibility, 0 to 1, as a fraction of
time the Sun is visible. Use the **GeoTIFF**, not the raw IMG.

**Elevation** — LOLA `LDEM_85S_10M_FLOAT`, 10 m/px, from the PDS geosciences node. The pipeline
does **not** read the raw download: it reads `Altitude-rasterize.tif`, a QGIS-processed version
converted from km to m. Raw values are radius against a 1737.4 km reference sphere.

## Gotchas — each of these cost an evening

**Units, elevation.** The DEM stores kilometres against a 1,737,400 m reference sphere. Slope
calculations need metres, because the pixel spacing is in metres. Getting this wrong makes
slope wrong by 1000x and it still runs without error. `ALTITUDE_OFFSET = 1737400` and
`radius_to_elevation()` handle the offset; the km-to-m conversion happens in QGIS upstream.

**Units, distance.** `distance_transform_edt` returns distance in _pixels_ by default. Pass the
`sampling` argument with the pixel size so it returns metres.

**Units, slope.** `np.gradient` assumes spacing of 1 unless told otherwise. The pixel size must
be passed, and it is passed per axis in axis order: axis 0 (rows, y) first, then axis 1
(columns, x). Pixels are square (60 m) so this currently makes no numerical difference, but the
argument order is latent.

**Illumination scale factor.** Stored as scaled integers; true value is DN x 0.00004. QGIS
applies this automatically on display, rasterio's `.read(1)` does **not**. Pull the factor from
`src.scales[0]` rather than hardcoding it. Shadow (0) is 0 either way, but every threshold above
zero is meaningless without it.

**distance_transform_edt polarity.** It measures, for each True pixel, distance to the nearest
False pixel. So whatever you are measuring _toward_ must be False in the input. To get
"distance to nearest labelled region", pass `labeled_array == 0`, not `> 0`.

**ndimage.label ignores value distinctions.** It treats any nonzero as foreground. A three-state
array (0/1/2) will not label the classes separately — it merges them. Label each mask
separately, in separate calls.

**Hemisphere and CRS.** Product filenames differ by a single character between north and south
(`85N` vs `85S`) and it is easy to download the wrong one — the symptom is a layer that loads
fine but sits on the opposite pole and never appears on canvas. Separately, the raw PDS
illumination `.LBL` carries `CENTER_LATITUDE = 90` on a _south_ polar product, which is an error
in the label; GDAL believes it and builds a north polar CRS. The PGDA GeoTIFFs do not have this
problem, which is why they are preferred.

**NaN and nodata.** Source nodata must be passed to `reproject` as `src_nodata`/`dst_nodata`, or
`Resampling.average` blends the fill sentinel (-3.4e38) into real elevations at the edges. After
resampling, nodata is converted to `np.nan`. Use `np.nanmin`/`np.nanmax` for checks — plain
`.min()` returns NaN if any NaN is present.

**Verify every raster on load.** Print band min/max and check they are physically plausible
before doing anything else. Elevation in metres: roughly -5500 to 7000. Illumination: 0 to ~0.88.
Slope: 0 to ~50 degrees. A boolean mask: only True/False. This project has repeatedly had files
whose names did not match their contents; the value range is the check that catches it.

**No Python loops over rasters.** 25.6 million pixels. Use vectorised numpy. A comparison like
`data > threshold` already returns a boolean array — no `np.where(..., True, False)` wrapper
needed.

**Suppressed warning.** rasterio 1.5.0 triggers a NumPy 2.5 shape deprecation in `.scales`.
Harmless, suppressed by message match at the top of `FileProccesing.py`. Do not broaden the
suppression to the whole DeprecationWarning category.

**Type checker false positives.** Pylance mis-infers scipy return types (e.g. `ndimage.label`
returns a tuple but is inferred as an int). Prefer unpacking (`labels, count = ...`) over
indexing, which sidesteps it. `# type: ignore` is used where scipy stubs are genuinely
incomplete.

## Settled decisions

**Illumination is a continuous score, not a binary mask.** The distribution has no clean natural
break, so thresholding discards real information — a 0.8 site genuinely beats a 0.55 one.

**8-connectivity for labelling.** Diagonal touches count as connected (all-ones 3x3 structure).

**Edge-to-edge distance, not centroid.** Proximity between a cold trap and a power site is
measured between nearest points, because that is what a cable or traverse route would span. A
centroid can misrepresent distance badly for large or irregular regions, and can even fall
outside the region.

**Downsample the DEM to 60 m rather than upsampling illumination to 10 m.** Upsampling would
invent illumination values that do not exist and manufacture apparent precision. The analysis
resolution is capped at 60 m by the illumination product regardless.

**Derive the PSR mask from illumination (`== 0`) rather than downloading LPSR.** This is the
method used in the literature. The published LPSR product is kept for validation, not as the
working mask.

## Open questions

**Lit threshold is not settled.** Evidence so far: illumination is a broad plateau from 0 to
~0.45, then a sharp decline, then a thin tail to a maximum of ~0.88. Only 19 pixels exceed 0.8.
18 million pixels sit between 0.1 and 0.9. The 99th percentile of lit pixels is ~0.48, which
coincides with the cliff. Candidate approaches: cut at the cliff (~0.45-0.5), use a percentile,
or avoid a hard threshold entirely given the continuous-score decision. Currently 0.44 in code,
provisionally.

**Scoring weights.** Factors are distance to power, illumination quality of the paired site,
slope, and cold trap area. They are in wildly different units and must be normalised (0-1)
before any weighted sum, or distance in metres will swamp everything. Weights should be
parameters with defaults, not hardcoded, so sensitivity can be tested — if the top site flips
when a weight is nudged, that is itself a finding.

**Hard constraints vs soft scores.** Slope above some angle and area below some minimum may
disqualify a site outright rather than merely lowering its score. Filtering first, then scoring
survivors, is likely cleaner.

**Midpoint / accessibility surface.** An alternative to discrete pairing: compute
distance-to-nearest-PSR and distance-to-nearest-PEL, then combine per pixel (max of the two is
probably better than the sum) to get a continuous accessibility surface. Complements the pairing
table rather than replacing it.

## Findings so far

Polar illumination is a continuum, not cleanly bimodal. Ground-level illumination maxes at
~0.88, below the 0.9+ figures implied by "peaks of eternal light" language — those figures
generally refer to specific points, sometimes modelled above ground level, at finer resolution.
Genuinely well-lit terrain at ground level is scarce.

## Validation still to do

Compare the derived PSR mask against the published LOLA LPSR product and quantify agreement.
Compare derived slope against QGIS `Raster > Analysis > Slope` on the same DEM. When ranking
runs, Shackleton's rim-to-floor pairing should score highly — the literature places peaks of
near-eternal light on its western rim, so it is the textbook case and a good ground truth.

## Known limitations to state in the write-up

60 m resolution caps the analysis; boulder-scale hazards (metre-scale) are not in this data at
all. Permanent shadow indicates where ice _can_ survive, not that ice is present — that requires
LEND hydrogen and Diviner temperature data. Slope is undirected (a crater rim and a conical peak
of equal steepness are indistinguishable); basin-versus-peak comes from elevation, not slope.
Distances are straight-line and ignore terrain, so real traverse cost is higher. Illumination is
ground-level and time-averaged over a lunar precession cycle.

## Working preferences

Do not write the project notes, README prose, or write-up content — provide structure,
frameworks, and questions instead. The act of writing is what imprints the material. Code and
tooling config are fine to write.

Be direct and critical. Identify what holds up and what does not, without softening.

Prefer explaining the concept behind a fix over supplying the fix, where there is a choice.
