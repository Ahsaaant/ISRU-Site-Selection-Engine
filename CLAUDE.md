# ISRU Site Selection Engine

Identifies candidate lunar base locations near the Moon's south pole by pairing permanently
shadowed regions (PSRs — cold traps, where water ice can survive) with nearby highly lit regions
(HLRs/PELs — viable solar power sites).

The core problem: the Moon's small axial tilt (~1.5 degrees) means crater floors near the pole
never see sunlight, while nearby rims and ridges are lit almost continuously. Ice needs darkness;
power needs light. They are mutually exclusive by location, so a viable base needs both, close
together. Site selection is therefore a proximity problem.

## Current state

Phase 0 (data acquisition and alignment): complete.
Phase 1 (elevation, slope, illumination, PSR/HLR masks): complete.
Phase 2 (label regions, sizes, per-region tables, distance transforms): complete.
Phase 3 (pairing table, scoring rubric, ranking): pairing function written and passing on test
data, not yet run on the real rasters. Scoring not started.
Phase 4 (write-up): not started.

Rule: no phase begins until the previous one is committed and pushed.

## Structure

```
src/Main.py             orchestration; runs the pipeline
src/FileProccesing.py   raster I/O, resampling, slope, illumination scaling, plotting
src/Regions.py          validity mask, region labelling, sizes, per-region tables, distance maps
src/Analysis.py         pairing table; will hold scoring
data/                   gitignored — rasters are hundreds of MB to GB
```

Note the existing spelling of `FileProccesing.py` — keep it consistent or rename everywhere.

## Data

Both products cover 85 degrees S to the pole. Everything is resampled onto the **60 m illumination
grid (5058 x 5058)**, which is the analysis resolution.

**Illumination** — LOLA `AVGVISIB_85S_060M_201608`, 60 m/px, from PGDA
(pgda.gsfc.nasa.gov/products/69). Average solar visibility as a fraction of time the Sun is
visible. Use the **GeoTIFF**, not the raw IMG.

**Elevation** — LOLA `LDEM_85S_10M_FLOAT`, 10 m/px, from the PDS geosciences node. The pipeline
does **not** read the raw download: it reads `Altitude-rasterize.tif`, a QGIS-processed version
converted from km to m. Raw values are radius against a 1737.4 km reference sphere.

## Known live bug — resolve before scoring

`scaled_illumination_data.max()` returns **~0.88 (a 0–1 fraction)**, but `PEL_THRESHOLD` in
Main.py is **55**, and the PEL region table shows mean illumination values around 55. These are
inconsistent — a threshold of 55 against 0–1 data should select nothing, yet regions are being
found. Something is scaling twice, or scaling at the wrong point in the pipeline. Trace it before
building any scoring on the illumination column. Evidence from the histogram work (all in
fractions): max 0.88, 99th percentile of lit pixels ~0.48, broad plateau to ~0.45 then a sharp
decline, only 19 pixels above 0.8.

## Gotchas — each of these cost an evening

**Units, elevation.** The DEM stores kilometres against a 1,737,400 m reference sphere. Slope
needs metres because pixel spacing is in metres. Wrong by 1000x and it still runs silently.
`ALTITUDE_OFFSET = 1737400` and `radius_to_elevation()` handle the offset; the km-to-m conversion
happens in QGIS upstream.

**Units, distance.** `distance_transform_edt` returns pixels by default. Pass `sampling` with the
pixel size (60) so it returns metres. Pass it by keyword, not positionally.

**Units, slope.** `np.gradient` assumes spacing of 1 unless told otherwise. Pixel size must be
passed, per axis, in axis order: axis 0 (rows, y) first, then axis 1 (columns, x). Pixels are
square so this currently makes no numerical difference, but the argument order is latent.

**Illumination scale factor.** Stored as scaled integers; true value is DN x 0.00004. QGIS applies
this on display, rasterio's `.read(1)` does not. Pull it from `src.scales[0]`, never hardcode.

**distance_transform_edt polarity.** Measures, for each True pixel, distance to the nearest False
pixel. Whatever you measure *toward* must be False. For "distance to nearest region", pass
`labels == 0` or `array != region_id`, not the region itself.

**ndimage.label ignores value distinctions.** Treats any nonzero as foreground. A three-state
array (0/1/2) will not label classes separately — it merges them. Label each mask separately.

**bincount includes the background at index 0.** `np.bincount(labels.ravel())` returns sizes
indexed by region ID, with index 0 holding the (huge) background pixel count. Slice the *output*
(`[1:]`), never the input array. Slicing `labels.ravel()[1:]` drops one pixel and leaves the
background intact — a real bug that produced 25-million-pixel "regions". After slicing, remember
indices shift by one relative to label IDs.

**ndimage statistics need the real index list.** `ndimage.mean/minimum/center_of_mass` take
(values, labels, index). Pass the *filtered* region IDs (`Table.index`), not
`np.arange(1, count+1)` — filtered tables have gaps and arange silently misaligns everything.

**Per-pixel vs per-region data.** Rasters (illumination, elevation, slope) go through
`ndimage.mean` to become columns. Sizes and IDs are already per-region and get assigned to the
DataFrame directly. Passing a per-region array to `ndimage.mean` throws a broadcast error.

**pandas index inheritance.** Building a DataFrame from arrays that already carry an index gives
you a duplicate ID column plus an inherited index. Pick one convention — region_id as column or
as index — and use it consistently.

**Hemisphere and CRS.** Product filenames differ by one character between poles (`85N` vs `85S`);
the wrong one loads fine but sits on the opposite pole and never appears on canvas. The raw PDS
illumination `.LBL` carries `CENTER_LATITUDE = 90` on a *south* polar product — GDAL believes it
and builds a north polar CRS. PGDA GeoTIFFs don't have this problem, which is why they're used.

**NaN and nodata.** Source nodata must be passed to `reproject` as `src_nodata`/`dst_nodata`, or
`Resampling.average` blends the fill sentinel (-3.4e38) into real elevations at the edges. After
resampling, nodata becomes `np.nan`. Use `np.nanmin`/`np.nanmax` — plain `.min()` returns NaN if
any NaN is present. Slope's NaN extends *wider* than elevation's, because `np.gradient` needs
neighbours.

**Validity mask.** Built from all layers (`~np.isnan(...)` ANDed together) and applied to the
masks *before* labelling, so no region can exist where any layer lacks data. Without it, edge
regions produce NaN means that survive into the table and would propagate to NaN scores.

**Verify every raster on load.** Print band min/max and check plausibility before anything else.
Elevation in metres: roughly -5500 to 7000. Illumination: 0 to ~0.88. Slope: 0 to ~50 degrees. A
boolean mask: only True/False. This project has repeatedly had files whose names did not match
their contents; the value range is the check that catches it.

**No Python loops over rasters.** 25.6 million pixels. Vectorised numpy only. A comparison like
`data > threshold` already returns a boolean array — no `np.where(..., True, False)` wrapper. A
loop over ~150 regions is fine; a loop over pixels is not.

**Suppressed warning.** rasterio 1.5.0 triggers a NumPy 2.5 shape deprecation in `.scales`.
Harmless, suppressed by message match. Do not broaden to the whole DeprecationWarning category.

**Type checker false positives.** Pylance mis-infers scipy return types (`ndimage.label` returns a
tuple, inferred as int). Prefer unpacking over indexing, which sidesteps it. `# type: ignore`
where stubs are genuinely incomplete.

## Settled decisions

**Illumination is a continuous score, not a binary mask** for scoring purposes. The distribution
has no clean natural break, so thresholding discards real information.

**8-connectivity for labelling.** Diagonal touches count as connected (all-ones 3x3 structure).

**Edge-to-edge distance, not centroid.** Measured via `ndimage.minimum` on a distance map, because
that is what a cable or traverse route would span. Centroids misrepresent large or irregular
regions and can fall outside them.

**Minimum region size: 10 pixels (36,000 m²).** Labelling produces ~54,000 PSR regions, the
overwhelming majority single-pixel speckle. Filter applied at the table level, before pairing.

**Feasibility distance: 2000 m.** The radial limit for astronauts without a rover
(doi 10.1029/2025JE009434). Note this models *crew walkback*, not cable runs or rover traverses —
a different architecture would justify a different threshold.

**Pairing table is long format, IDs only.** One row per (PEL, PSR, distance) triple. A PSR
appearing near several PELs gets several rows. Region properties live in the region tables and are
joined back by ID — do not denormalise.

**Downsample the DEM to 60 m rather than upsampling illumination to 10 m.** Upsampling would
invent illumination values and manufacture apparent precision. Analysis is capped at 60 m by the
illumination product regardless.

**Derive the PSR mask from illumination (`== 0`) rather than downloading LPSR.** This is the
method used in the literature. The published LPSR product is kept for validation.

## Open questions

**Scoring weights.** Factors: distance, illumination quality of the paired PEL, slope, PSR area.
Wildly different units — must be normalised to 0–1 before any weighted sum, and inverted where
lower is better, or distance in metres swamps everything. Weights should be parameters with
defaults so sensitivity can be tested. If the top site flips when a weight is nudged, that is
itself a finding; if the same sites stay on top across weightings, that is robustness and a
stronger claim than the ranking.

**Hard constraints vs soft scores.** Slope above some angle and area below some minimum may
disqualify a site outright rather than lowering its score. Filter first, score survivors.

**Slope measurement point.** Currently mean slope across the whole region. Alternatives: slope at
the centroid, or mean slope along the route between paired regions. Each answers a different
question and the choice is unrecorded.

**Accessibility surface.** An alternative to discrete pairing: combine distance-to-nearest-PSR and
distance-to-nearest-PEL per pixel (max of the two, probably, rather than sum) for a continuous
surface. Complements the pairing table rather than replacing it.

## Findings so far

Polar illumination is a continuum, not cleanly bimodal — 18 million pixels sit in the "gap" that
looks empty on a linear histogram. Ground-level illumination maxes at ~0.88, below the 0.9+ implied
by "peaks of eternal light" language; those figures generally refer to specific points, sometimes
modelled above ground level, at finer resolution. Genuinely well-lit terrain at ground level is
scarce — at a 0.75 threshold the largest contiguous lit region was 7 pixels.

## Validation still to do

Compare the derived PSR mask against the published LOLA LPSR product and quantify agreement.
Compare derived slope against QGIS `Raster > Analysis > Slope` on the same DEM. When ranking runs,
Shackleton's rim-to-floor pairing should score highly — the literature places peaks of near-eternal
light on its western rim, so it is the textbook case and a good ground truth.

Immediate checks when the pairing table first runs on real data: a PSR appearing with two PELs must
show two *different* distances (identical means the mask isn't updating); row count should be
neither near-zero nor tens of thousands; and one pairing should be spot-checked against the plotted
maps by eye. If very few PSRs have any PEL within 2 km, that challenges the project's core premise
and needs investigating before scoring.

## Known limitations to state in the write-up

60 m resolution caps the analysis; boulder-scale hazards are not in this data at all. Permanent
shadow indicates where ice *can* survive, not that ice is present — that requires LEND hydrogen and
Diviner temperature data. Slope is undirected (a crater rim and a conical peak of equal steepness
are indistinguishable); basin-versus-peak comes from elevation. Distances are straight-line and
ignore terrain, so real traverse cost is higher — this matters especially given the threshold
models crew walkback. Illumination is ground-level and time-averaged over a lunar precession cycle.

## Working preferences

Do not write the project notes, README prose, or write-up content — provide structure, frameworks,
and questions instead. The act of writing is what imprints the material. Code and tooling config
are fine to write.

Be direct and critical. Identify what holds up and what does not, without softening.

Prefer explaining the concept behind a fix over supplying the fix, where there is a choice.
