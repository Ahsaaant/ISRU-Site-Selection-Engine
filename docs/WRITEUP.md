# Where on the Moon can you have both ice and power?

An analysis of the lunar south pole for in-situ resource utilisation site selection, using LOLA
illumination and elevation data at 60 m resolution.

---

## 1. The problem

The Moon's axial tilt is about 1.5 degrees. On Earth, 23.4 degrees of tilt gives us seasons; on
the Moon, 1.5 degrees gives us something stranger. Near the poles, the Sun never rises far above
the horizon, so topography decides everything. Crater floors deep enough to hide from that
grazing light have not seen sunlight in perhaps two billion years. The rims and ridges beside
them are lit almost continuously.

Both conditions are valuable, for opposite reasons.

The permanently shadowed regions — PSRs — are cold traps. Surface temperatures below about 110 K
allow water ice to survive against sublimation on geological timescales. If there is accessible
water on the Moon, it is there. Water means drinking water, breathable oxygen, and hydrogen and
oxygen propellant, none of which then has to be lifted out of Earth's gravity well.

The highly lit regions — variously peaks of eternal light, PELs, or peaks of near-eternal light —
are where solar power works. A lunar night is fourteen Earth days long. Surviving one on stored
energy is a serious engineering problem; avoiding it entirely is far cheaper. A site with 60%
average solar visibility and short eclipse periods needs a fraction of the battery mass of a site
on the equator.

The difficulty is that these two conditions are mutually exclusive **by definition**. A pixel
cannot be both permanently shadowed and permanently lit. So a viable base cannot sit on both —
it has to sit *between* them, close enough to each that the same crew and the same infrastructure
can reach both.

That makes site selection a proximity problem, and proximity problems are tractable. This project
builds the answer from published data.

---

## 2. Data and method

### Inputs

Two LOLA products, both covering 85°S to the pole.

**Illumination.** `AVGVISIB_85S_060M_201608` from the Planetary Geodesy Data Archive: average
solar visibility per 60 m pixel, expressed as the fraction of a lunar precession cycle during
which the Sun is visible from that point at ground level. This is the analysis grid — 5,058 ×
5,058 pixels, 92,027 km².

**Elevation.** `LDEM_85S_10M_FLOAT` from the PDS Geosciences node, at 10 m/px. Values are radii
from the Moon's centre against a 1,737.4 km reference sphere, distributed in kilometres.

The DEM is downsampled to the 60 m illumination grid rather than the illumination being
upsampled to 10 m. Upsampling would invent illumination values the product does not contain and
manufacture apparent precision. The analysis is capped at 60 m by the illumination product
regardless of what the DEM offers, so the honest move is to say so in the grid.

### Deriving the layers

Elevation comes from subtracting the reference sphere radius. Slope is the arctangent of the
gradient magnitude, in degrees, with the true 60 m pixel spacing passed per axis. A validity
mask is built from all three layers and applied before anything is labelled, so no region can
exist where any layer lacks data — 99.921% of the grid survives.

### Defining the two classes

PSRs are pixels where average solar visibility is **exactly zero**. This is the definition used
in the literature and it needs no threshold: a pixel that never sees the Sun over a full
precession cycle is a cold trap.

PELs need a threshold, and choosing it turned out to be the most consequential decision in the
project. That is section 4.

Both masks are labelled with 8-connectivity, so diagonal touches count as connected. Regions of
10 pixels or fewer are dropped as speckle — labelling the PSR mask produces 54,478 regions, the
overwhelming majority single pixels.

### Pairing and scoring

For each PEL, a Euclidean distance transform gives the **edge-to-edge** distance to every nearby
PSR. Edge-to-edge rather than centroid-to-centroid, because that is what a cable or a traverse
route actually spans; the centroid of a large or crescent-shaped region can fall outside the
region entirely.

Hard constraints are applied before scoring, not as penalties within it. A PEL with a mean slope
above 15 degrees is not buildable and a PSR below 1 km² is not worth mining, and neither should
be able to climb the ranking on the strength of another factor.

Surviving pairs are scored on four factors, each rescaled to 0-1 and inverted where lower is
better:

| Factor | Direction | Weight | Rationale |
| --- | --- | --- | --- |
| Distance | lower better | 0.35 | The premise of the project |
| PEL illumination | higher better | 0.30 | Power availability, and the scarcer resource |
| PSR area | higher better | 0.20 | Proxy for how much ice could be there; log-rescaled |
| PEL slope | lower better | 0.15 | Buildability, partly handled by the hard constraint |

The rescaling is not cosmetic. Distance runs to thousands of metres, slope to tens of degrees,
illumination to 88 percent, and PSR area across three orders of magnitude. Summed raw, the score
would be distance plus rounding error.

---

## 3. The main result: co-location is rare

**Of 5,303 cold traps larger than 10 pixels, 63 have any PEL within 2 km. That is 1.2%.**

The median cold trap is **28.9 km** from the nearest peak of eternal light. The distribution:

| Within | PSRs (of 5,303) | Share |
| --- | --- | --- |
| 500 m | 11 | 0.2% |
| 1 km | 27 | 0.5% |
| 2 km | 63 | 1.2% |
| 5 km | 203 | 3.8% |
| 10 km | 565 | 10.7% |
| 20 km | 1,565 | 29.5% |

Applying the viability constraints — PSR at least 1 km², PEL at most 15 degrees mean slope —
leaves 481 cold traps, of which **five** have a PEL within 2 km and **none** within 1 km. Those
five produce ten candidate sites.

This deserves to be stated plainly rather than buried as a limitation: the premise that ice and
power are mutually exclusive by location holds far more strongly than a casual reading of the
literature suggests. The interesting question is not "which of the many co-located sites is
best" but "do any exist at all". Ten do.

The scarcity is not an obstacle to the analysis. It **is** the analysis. A search that returned
thousands of viable sites would be telling you that the constraint you imposed was not binding,
and therefore that you had learned nothing about the terrain.

---

## 4. Why the PEL threshold is the load-bearing decision

PSRs need no threshold. PELs do, and the result is unusually sensitive to it.

Sweeping the threshold and labelling at each value:

| Threshold | Regions >10 px | Largest region |
| --- | --- | --- |
| 40% | 1,587 | **4,066 km²** |
| 45% | 1,931 | **503 km²** |
| 50% | 1,155 | 4.5 km² |
| **55%** | **131** | **0.36 km²** |
| 60% | 34 | 0.15 km² |
| 65% | 7 | 0.086 km² |
| 70% | 1 | 0.040 km² |

There is a **percolation transition between 50% and 45%**. Above it, the lit terrain resolves
into discrete peaks. Below it, the ridge network connects into a single sprawling component
thousands of square kilometres in extent. A "region" of 4,066 km² is not a site; it is the
observation that most of the polar highlands are moderately lit and touch each other.

So the threshold is squeezed from both sides. Below about 50% the class stops meaning anything.
Above 60% there is almost nothing left to rank — at 70% the entire map contains one region of
eleven pixels. The usable band is narrow, and 55% sits in the middle of it.

This connects to a finding from earlier in the project: polar illumination is a **continuum, not
two populations**. The histogram shows a broad plateau out to roughly 45% and then a steep,
smooth decline with no natural break anywhere. Twenty-two million pixels — 86% of the mapped
area — sit between 0% and 45%, the range that looks empty on a linear axis. There is no threshold that carves nature at a joint, because there
is no joint.

That is also why illumination is carried into the score as a continuous value rather than being
reduced to the binary mask. The mask defines *which regions are candidates*; the mean
illumination decides *how good each one is*. Thresholding twice would discard real information.

One consequence worth recording: computing the illumination percentage in float32 rather than
float64 changes the PEL count from 1,890 to 1,886, because four regions sit within rounding
distance of the cut. That is not a bug. It is what thresholding a continuum looks like up close.

---

## 5. Results

### The ranked sites — 2 km walkback tier

| Rank | Pair | Distance | PEL illum. | PEL slope | PSR area | Score |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | PSR 24969 – PEL 852 | 1,195 m | 59.2% | 4.0° | 234.4 km² | 0.68 |
| 2 | PSR 24969 – PEL 985 | 1,655 m | 64.2% | 3.4° | 234.4 km² | 0.65 |
| 3 | PSR 24969 – PEL 1001 | 1,697 m | 64.4% | 3.1° | 234.4 km² | 0.64 |
| 4 | PSR 25131 – PEL 808 | 1,342 m | 64.9% | 5.6° | 1.9 km² | 0.59 |
| 5 | PSR 27173 – PEL 897 | 1,380 m | 62.1% | 3.2° | 1.1 km² | 0.52 |
| 6 | PSR 43063 – PEL 1635 | 1,370 m | 58.1% | 2.2° | 2.0 km² | 0.43 |
| 7 | PSR 24969 – PEL 1044 | 1,805 m | 58.8% | 2.0° | 234.4 km² | 0.40 |
| 8 | PSR 24969 – PEL 1039 | 1,832 m | 59.4% | 3.0° | 234.4 km² | 0.38 |
| 9 | PSR 36252 – PEL 1266 | 1,557 m | 58.8% | 1.6° | 1.0 km² | 0.35 |
| 10 | PSR 36252 – PEL 1291 | 1,832 m | 57.3% | 1.4° | 1.0 km² | 0.15 |

**PSR 24969 is Shackleton's shadowed floor.** It is 234 km² of permanent shadow beginning
1.96 km from the pole and extending to 19.6 km, and it takes five of the ten places including
the top three.

This matters because it was not put there. The pipeline has no concept of Shackleton, no crater
catalogue in its scoring path, and no knowledge that the literature has placed peaks of
near-eternal light on Shackleton's western rim for two decades. It ranked the textbook site first
from the data alone. That is the strongest single piece of evidence that the method works.

The pole detail figure shows why. Shackleton's floor is a clean shadowed disc; the PELs form a
**thin ring around its rim**, exactly as described in the literature. The south pole marker sits
on that rim, which is the standard description of its position.

### The best-lit spot is 293 m out of reach

The single best-lit region in the entire dataset — PEL 840, at **70.09%** average solar
visibility — sits **2,293 m** from Shackleton's shadow. The walkback limit is 2,000 m.

The best power site on the map misses the best cold trap by less than 300 metres. Under the 2 km
tier it does not appear at all; relax to 5 km and it becomes the top-ranked site outright. It is
a clean illustration of how much the ranking depends on an assumption about mission architecture
rather than about terrain.

### Distance tiers

The 2 km figure is a crew walkback limit — how far an astronaut can walk from a pressurised
refuge and still return unassisted. It is a property of one mission architecture, not of the
Moon. Running the same analysis under three assumptions:

| Tier | Assumption | Sites | Distinct PSRs | Distinct PELs |
| --- | --- | --- | --- | --- |
| 2 km | Unassisted crew traverse | 10 | 5 | 10 |
| 5 km | Pressurised rover | 77 | 27 | 61 |
| 10 km | Power cable to a remote extraction site | 246 | 60 | 117 |

A twenty-fivefold increase in candidate sites from a fivefold relaxation of one assumption.
Anyone quoting a site count from this kind of analysis should be asked which architecture they
assumed.

### Does the ranking survive its weights?

Weights chosen by judgement are the weakest part of any scoring rubric, so they were tested
rather than defended. Drawing 2,000 random weightings from a flat Dirichlet distribution and
recording how often each site lands in the top five:

| Site | In top 5 | Best rank | Median rank |
| --- | --- | --- | --- |
| PSR 24969 – PEL 1001 | 86.6% | 1 | 2 |
| PSR 24969 – PEL 985 | 85.4% | 1 | 3 |
| PSR 24969 – PEL 852 | 84.6% | 1 | 3 |
| PSR 24969 – PEL 1044 | 52.0% | 1 | 5 |
| PSR 27173 – PEL 897 | 49.5% | 1 | 6 |
| PSR 25131 – PEL 808 | 45.8% | 1 | 6 |

Three sites — all Shackleton pairings — hold places in the top five roughly 85% of the time. Pushing each
factor to a dominant 0.7 weight in turn puts a Shackleton pairing first in three of the four
corners. The exception is slope-dominant, which surfaces PSR 36252 – PEL 1266, a 1.6-degree PEL
beside a cold trap two hundred times smaller.

So the specific ordering of ranks 1-3 is weight-dependent and should not be quoted. The
conclusion that **Shackleton is the site** is not. That robustness is a stronger claim than any
particular ranking would have been.

---

## 6. Validation

Every check that could be run without additional data was run.

**Six catalogued cold traps located.** Shackleton, de Gerlache, Shoemaker, Haworth, Faustini and
Sverdrup were converted from latitude and longitude into pixel coordinates through the polar
stereographic projection and tested against the derived mask. All six land on large PSRs —
Shoemaker at 1,085 km², Haworth at 1,029 km², Faustini at 668 km², Sverdrup at 556 km².

Matching is by proximity to the largest nearby region rather than by strict point containment,
for a specific reason. Shackleton's catalogued centre, 89.9°S 0.0°E, lies about 3 km from the
pole, where a fraction of a degree of longitude swings the point clear across the crater. A point
test fails there for reasons that have nothing to do with the mask being wrong. In this data
Shackleton's floor centres about 10 km from the pole, which is precisely why the pole lies on its
rim.

**A control run confirmed the projection convention.** Repeating the test with longitudes
mirrored — treating west as positive — drops the hit rate from six of six to one of six, and the
one survivor is Haworth at 355°E, which is nearly symmetric about the prime meridian and lands
close either way. That asymmetry is what makes the original result meaningful rather than
coincidental. Given this project's history of hemisphere and CRS problems, it was worth running.

**Slope validated against Horn's method.** The pipeline computes slope with `np.gradient`, a
two-point central difference along each axis. Horn's method — the third-order algorithm GDAL and
QGIS both use — takes a weighted average over all eight neighbours. Implementing it directly gave
an in-process comparison with no manual export step:

- correlation **0.9983**
- mean absolute difference **0.257°**, median **0.185°**
- 95th percentile of absolute difference **0.73°**

Horn's implementation was itself checked against an analytic cone of known gradient, returning
5.710° against a true 5.711°. The largest single disagreement, 15.6°, is at isolated spikes where
the smoothing behaviour of the two algorithms genuinely differs — which is the expected direction.

**Pairing sanity checks.** The pairing loop rebuilds a mask per PEL, and the most likely way for
it to be silently wrong is for that mask never to update, which would give every PSR the same
distance to every PEL. Of 31 PSRs pairing with more than one PEL, **zero** show a single repeated
distance. Three contain an individual tie, which is ordinary quantisation: a distance transform
on a regular grid returns `60 × √integer`, so exact ties between distinct regions are expected.
The check was confirmed to fail on a deliberately broken input, so it can detect what it exists
to detect.

**Extent.** The derived PSR mask covers 9,880 km², 10.74% of the mapped area.

**Not done.** The derived mask has not been compared against the published LOLA LPSR product,
which is not held locally. That comparison remains the most valuable outstanding check, and
9,880 km² over 85°S to the pole is the number to compare against.

---

## 7. Limitations

**Resolution.** Everything is capped at 60 m by the illumination product. Boulder-scale hazards,
which decide whether a lander can actually set down, are not in this data at all.

**Shadow is not ice.** A permanently shadowed region is where water ice *can* survive, not
evidence that any is present. Establishing that needs LEND neutron and Diviner temperature data,
neither of which is used here. Every "cold trap" in this analysis is a thermal argument, not a
detection.

**Slope is undirected.** The magnitude of the gradient does not distinguish a crater rim from a
conical peak of equal steepness. Basin-versus-peak character comes from elevation, which is
carried in the region tables but not scored.

**Distances are straight-line.** No terrain cost, no obstacle avoidance, no elevation change
along the path. Real traverse distance exceeds these figures, and the gap matters most precisely
where the threshold is a walkback limit — an astronaut walking 2 km of straight-line distance
across a crater rim is doing considerably more than 2 km of work. All ten sites should be read as
optimistic.

**Illumination is ground-level and time-averaged.** Averaged over a full precession cycle, it
says nothing about the *duration* of individual eclipse periods, which is what actually sizes a
battery. Two sites with identical 60% averages can have very different worst-case night lengths.
Ground level also explains why the maximum here is 88.4% rather than the 90%+ implied by "peak of
eternal light" language: the higher published figures generally refer to specific points, often
modelled several metres above the surface where a tower would put a panel, at finer resolution.

**Scores are comparative, not absolute.** A 0.68 means best of ten, under one weighting, against
this candidate set. It is not a rating of the site against any external standard.

**The headline tier rests on five cold traps.** With five distinct PSRs producing ten pairs, the
ranking is short by nature and the tail is thin.

---

## 8. What would be worth doing next

**Compare against LPSR.** The single highest-value outstanding check, and the one that would
convert "the mask looks right" into "the mask agrees with the published product to within X".

**Bring in LEND and Diviner.** This would move the analysis from where ice *can* be to where it
plausibly *is*, which is the difference between a thermal argument and a resource estimate.

**Path-aware distance.** Replace the Euclidean transform with a least-cost path over the slope
raster. This would matter most for exactly the sites that rank highest, since Shackleton's rim is
steep, and would likely reorder the top five.

**An accessibility surface.** Rather than discrete pairing, compute per pixel the maximum of
distance-to-nearest-PSR and distance-to-nearest-PEL. The result is a continuous surface whose
minima are the best-placed points on the map, found without committing to a threshold at all. It
would complement the pairing table rather than replace it, and both input distance maps already
exist.

**Eclipse duration, not just average.** Longest continuous dark period per pixel is the number
that sizes the battery, and average solar visibility is a poor proxy for it.

---

## 9. Conclusion

Ten sites at the lunar south pole satisfy all of: a cold trap of at least 1 km², a buildable peak
of eternal light above 55% average solar visibility, and no more than 2 km between them. Five
distinct cold traps produce those ten.

Six of the ten involve Shackleton crater, including the top three, and Shackleton pairings hold
the top of the ranking across roughly 85% of two thousand randomly drawn weightings. The analysis
converges on the site the literature has favoured for twenty years, from the data alone, without
being told it should.

The more interesting number is 1.2%. That is the fraction of the south pole's cold traps with any
peak of eternal light within walking distance, and it is the real finding here. Ice and power at
the lunar pole are not merely separate — they are almost never adjacent. The median cold trap is
nearly 29 kilometres from the nearest good power site. The handful of places where the two come
within walking distance of each other are, on this evidence, among the most strategically
valuable real estate on the Moon.

---

*Analysis: LOLA `AVGVISIB_85S_060M_201608` and `LDEM_85S_10M_FLOAT`, 60 m grid, 85°S to the pole.
Figures and tables in `output/`. Reproduce with `python src/Main.py`.*

*A formatted version of this write-up, with interactive charts, is published at*
*<https://claude.ai/code/artifact/b4134845-6562-4812-bc3a-7e759265ddc7> (private until shared).*
