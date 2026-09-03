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
Phase 3 (pairing table, scoring rubric, ranking): complete. Pairing, hard constraints,
normalised weighted scoring, three distance tiers, and a weight sensitivity sweep all run on
the real rasters. Outputs in `output/`.
Phase 4 (write-up): complete. `docs/WRITEUP.md`.

Rule: no phase begins until the previous one is committed and pushed.

## Structure

```
src/Main.py             orchestration; runs the pipeline
src/FileProcessing.py   raster I/O, resampling, slope, illumination scaling, plotting
src/Regions.py          validity mask, region labelling, sizes, per-region tables, distance maps
src/Analysis.py         pairing table, hard constraints, scoring, ranking, sensitivity
src/Validation.py       Horn slope, crater geolocation, pairing sanity checks
data/                   gitignored — rasters are hundreds of MB to GB
output/                 tracked — figures, tables, summary.json from the last full run
docs/WRITEUP.md         the write-up
```

The file is `FileProcessing.py`, one `c`. Earlier notes spelled it `FileProccesing.py`; that
rename is done and the old spelling survives only in stale references.

## Data

Both products cover 85 degrees S to the pole. Everything is resampled onto the **60 m illumination
grid (5058 x 5058)**, which is the analysis resolution.

**Illumination** — LOLA `AVGVISIB_85S_060M_201608`, 60 m/px, from PGDA
(pgda.gsfc.nasa.gov/products/69). Average solar visibility as a fraction of time the Sun is
visible. Use the **GeoTIFF**, not the raw IMG.

**Elevation** — LOLA `LDEM_85S_10M_FLOAT`, 10 m/px, from the PDS geosciences node. The pipeline
does **not** read the raw download: it reads `Altitude-rasterize.tif`, a QGIS-processed version
converted from km to m. Raw values are radius against a 1737.4 km reference sphere.

## Resolved: the illumination scale confusion

Previously recorded as a live bug: `scaled_illumination_data.max()` returning ~0.88 against a
`PEL_THRESHOLD` of 55. There was no double scaling. `scale_illumination_data` multiplies by the
raster scale factor **and by 100**, so the array is a percentage, 0 to 88.44, and a threshold of
55 is consistent with it. The 0.88 figure came from histogram work done before the `* 100`
existed. The note described an older state of the code, not the code.

The lesson worth keeping: when a recorded symptom stops reproducing, the note is a suspect
too. Check the code before trusting the file that describes it.

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
Elevation in metres: roughly -5500 to 7000. Illumination as a percentage: 0 to 88.44. Slope: 0
to ~54 degrees. A
boolean mask: only True/False. This project has repeatedly had files whose names did not match
their contents; the value range is the check that catches it.

**No Python loops over rasters.** 25.6 million pixels. Vectorised numpy only. A comparison like
`data > threshold` already returns a boolean array — no `np.where(..., True, False)` wrapper. A
loop over ~150 regions is fine; a loop over pixels is not.

**Illumination nodata is an integer sentinel, not NaN.** The illumination GeoTIFF is `int16`
with nodata `-32768`. `read_raster` does not convert it, so `validate_layers`, which tests
`~np.isnan(...)`, cannot see it — an int-derived array is never NaN. Scaled, the sentinel would
become -131.07 and pass `data <= PSR_THRESHOLD`, making every nodata pixel eligible as a PSR.
**This product happens to contain zero nodata pixels, so nothing is currently wrong.** It is a
trap for any future illumination raster that does have them.

**Float precision at the threshold boundary.** Computing the illumination percentage in float32
rather than float64 changes the PEL count from 1890 to 1886, because four regions sit within
rounding distance of the 55% cut. Main.py's path is float64. The sensitivity is not a bug; it is
what thresholding a continuum with no natural break looks like from close up.

**distance_transform_edt returns quantised distances.** On a regular grid, results are
`pixel_size * sqrt(integer)`. Exact ties between different regions are therefore common and are
*not* evidence of a stale mask. The real failure signature is one PSR showing the *same*
distance to *every* PEL it pairs with.

**Shackleton cannot be located by its catalogued centre.** Its cited centre, 89.9 S 0.0 E, lies
about 3 km from the pole, where a fraction of a degree of longitude swings the point across the
whole crater. A strict point-in-mask test fails there for reasons unrelated to the mask. In this
data Shackleton's floor centre is ~10 km from the pole, which is why the pole sits on its rim.
Match near-pole features by proximity to the largest nearby region, not by point containment.

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

**Hard constraints: PEL mean slope <= 15 degrees, PSR area >= 1 km².** Applied before scoring,
not as score penalties, so a disqualified region cannot be carried up the ranking by a strong
showing elsewhere. The slope limit currently rejects nothing — all 131 PELs are under 10 degrees
mean slope — which is itself informative: at 60 m resolution a ridge crest averages gentle.

**Slope measurement point: mean over the whole region.** Answers "is this region buildable",
matches the region table already built, and pairs with the slope hard constraint. Route slope
between paired regions would answer a different question and is not implemented.

**Scoring weights: distance 0.35, illumination 0.30, PSR area 0.20, slope 0.15.** Parameters
with defaults, renormalised to sum to 1. Reported alongside a 2000-draw Dirichlet sensitivity
sweep and four corner weightings, because whether the ranking survives reweighting matters more
than the ranking.

**Three distance tiers, not one.** 2 km walkback is the headline; 5 km (pressurised rover) and
10 km (power cable to a remote extraction site) are reported alongside. The 2 km limit is a
property of one mission architecture, not of the terrain, and running all three makes the
architecture assumption visible instead of baked in.

**Derive the PSR mask from illumination (`== 0`) rather than downloading LPSR.** This is the
method used in the literature. The published LPSR product is kept for validation.

## Open questions

**Accessibility surface.** Still open. An alternative to discrete pairing: combine
distance-to-nearest-PSR and distance-to-nearest-PEL per pixel (max of the two, probably, rather
than sum) for a continuous surface. Complements the pairing table rather than replacing it. Both
distance maps are already computed and written to `output/figures/`.

**Whether 55% is the right PEL threshold.** Defensible but not derived. See the percolation
finding below: the choice is constrained from below by percolation and from above by running out
of candidates, and 55% sits in a fairly narrow usable band rather than at a natural break.

**Resolved:** scoring weights, hard constraints, and slope measurement point are now recorded
under Settled decisions.

## Findings so far

**Co-location is rare, and that is the project's main result.** Only 63 of 5,303 PSRs above
10 px — 1.2% — have any PEL within 2 km. The median PSR sits 28.9 km from the nearest PEL. Of
the 481 PSRs above 1 km², five have a PEL within 2 km and none within 1 km. The premise that
ice and power are mutually exclusive by location holds much more strongly than expected; the
scarcity is the finding, not an obstacle to it.

**The PEL class only exists above about 50% illumination.** Below that the lit ridge network
percolates: thresholding at 45% gives a largest connected region of 503 km², and at 40% of
4,066 km². Above 50% the regions are discrete peaks — 4.5 km² largest at 50%, 0.36 km² at 55%.
So the threshold is bounded below by percolation and above by scarcity: 60% leaves 34 candidate
regions and 70% leaves one. The usable band is narrow.

**The ranking is robust to reweighting.** Across 2,000 random weightings, the top three sites
are all pairings of PSR 24969, the Shackleton complex, appearing in the top five 85-87% of the
time. Three of the four corner weightings put a PSR 24969 pairing first. The exception is
slope-dominant, which surfaces a flatter but far smaller cold trap.

**Validation passed on every check run.** Six catalogued cold traps — Shackleton, de Gerlache,
Shoemaker, Haworth, Faustini, Sverdrup — all land on large PSRs. The np.gradient slope layer
correlates 0.9983 with Horn's method with a mean absolute difference of 0.257 degrees. Derived
PSR extent is 9,880 km², 10.74% of the mapped area.

Polar illumination is a continuum, not cleanly bimodal — 18 million pixels sit in the "gap" that
looks empty on a linear histogram. Ground-level illumination maxes at ~0.88, below the 0.9+ implied
by "peaks of eternal light" language; those figures generally refer to specific points, sometimes
modelled above ground level, at finer resolution. Genuinely well-lit terrain at ground level is
scarce — at a 0.75 threshold the largest contiguous lit region was 7 pixels.

## Validation done, and still outstanding

**Done.** Six catalogued south polar craters located in the derived PSR mask, by proximity to
the largest nearby region (`Validation.check_known_cold_traps`). An east-positive longitude
control run confirmed the projection convention: mirrored, only one of six lands on a PSR.
Slope validated against Horn's method rather than QGIS — same algorithm GDAL and QGIS use, run
in-process, so no manual export step. Horn also checked against an analytic cone. The pairing
sanity checks CLAUDE.md specifies all pass on real data, and the distinct-distance check was
confirmed to fail on a deliberately broken example, so it can detect what it is there to detect.
Shackleton's rim-to-floor pairing ranks first, as the literature predicts.

**Still outstanding.** The derived PSR mask has not been compared against the published LOLA
LPSR product — that product is not held locally. Derived extent is 9,880 km² over 85 S to the
pole, which is the number to compare when LPSR is obtained.

## Known limitations to state in the write-up

60 m resolution caps the analysis; boulder-scale hazards are not in this data at all. Permanent
shadow indicates where ice *can* survive, not that ice is present — that requires LEND hydrogen and
Diviner temperature data. Slope is undirected (a crater rim and a conical peak of equal steepness
are indistinguishable); basin-versus-peak comes from elevation. Distances are straight-line and
ignore terrain, so real traverse cost is higher — this matters especially given the threshold
models crew walkback. Illumination is ground-level and time-averaged over a lunar precession cycle. Scores are
comparative within this candidate set only — a 0.68 is the best of ten, not an absolute rating.
The headline tier rests on five distinct cold traps, so the ranking is short by nature.

## Working preferences

Do not write the project notes, README prose, or write-up content — provide structure, frameworks,
and questions instead. The act of writing is what imprints the material. Code and tooling config
are fine to write.

Be direct and critical. Identify what holds up and what does not, without softening.

Prefer explaining the concept behind a fix over supplying the fix, where there is a choice.
