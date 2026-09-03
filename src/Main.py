import os, json
import numpy as np, pandas as pd
import rasterio
import matplotlib
matplotlib.use("Agg")  # write figures to disk without needing a display
import matplotlib.pyplot as plt

import FileProcessing as fp
import Regions as rg
import Analysis as an
import Validation as va

# Constants for file paths
ALTITUDE_RASTER_PATH = "data/Altitude-rasterize.tif"
ILLUMINATION_RASTER_PATH = "data/SunVisibility(abgvis_85S_060M_201608).tiff"
OUTPUT_DIRECTORY = "output"

# Constants for thresholds
PSR_THRESHOLD = 0    # A pixel is a PSR at or below this illumination percentage.
PEL_THRESHOLD = 55   # A pixel is a PEL above this illumination percentage.
REGION_SIZE_THRESHOLD = 10  # Regions of this many pixels or fewer are speckle and are dropped.

# Hard constraints. These disqualify a region outright rather than lowering its score, because
# a PEL too steep to build on and a PSR too small to be worth mining are not poor sites.
MAX_PEL_SLOPE = 15   # degrees, mean over the region; the usual construction and landing limit.
MIN_PSR_AREA = 1.0   # square kilometres; below this a cold trap is not a credible mining target.

# Constants for analysis
PIXEL_SIZE = 60           # The size of each pixel in metres.
FEASIBLE_DISTANCE = 2000  # Crew walkback limit in metres, doi 10.1029/2025JE009434.

# The walkback limit is a property of one mission architecture, not of the terrain. Each tier
# is the same analysis under a different assumption about how a crew or its power reaches the
# cold trap, so the effect of that assumption is visible rather than baked in.
DISTANCE_TIERS = {
    "walkback_2km": 2000,   # unassisted crew traverse, the headline case
    "rover_5km": 5000,      # pressurised rover
    "cable_10km": 10000,    # power transmitted to a remotely operated extraction site
}


def build_layers():
    """Loads the rasters and derives the elevation, illumination and slope layers."""

    print("== layers ==")
    illumination_data, illumination_scale_factor = fp.read_raster(ILLUMINATION_RASTER_PATH)
    resampled_altitude_data, pixel_size_x, pixel_size_y = fp.resample_raster(
        ALTITUDE_RASTER_PATH, ILLUMINATION_RASTER_PATH
    )

    elevation_data = fp.radius_to_elevation(resampled_altitude_data)
    scaled_illumination_data = fp.scale_illumination_data(illumination_data, illumination_scale_factor)
    slope_data = fp.elevation_to_slope(elevation_data, pixel_size_x=pixel_size_x, pixel_size_y=pixel_size_y)

    # Verify every raster on load. This project has repeatedly had files whose names did not
    # match their contents, and the value range is the check that catches it.
    for name, layer, expected in [
        ("elevation (m)", elevation_data, "roughly -5500 to 7000"),
        ("illumination (%)", scaled_illumination_data, "0 to ~88"),
        ("slope (deg)", slope_data, "0 to ~55"),
    ]:
        print(f"   {name:20s} min {np.nanmin(layer):10.2f}  max {np.nanmax(layer):10.2f}   expected {expected}")

    return scaled_illumination_data, elevation_data, slope_data


def build_regions(illumination_data, elevation_data, slope_data):
    """Labels the PSR and PEL regions and builds their per-region tables."""

    print("\n== regions ==")
    # Built from all layers and applied before labelling, so no region can exist where any
    # layer lacks data and produce a NaN mean that propagates into a NaN score.
    valid_map = rg.validate_layers([illumination_data, elevation_data, slope_data])
    print(f"   valid pixels {int(valid_map.sum()):,} of {valid_map.size:,} ({100 * valid_map.mean():.3f}%)")

    PSR_regions, PSR_region_count = rg.label_regions(
        illumination_data, valid_map, threshold=PSR_THRESHOLD, greater_than=False
    )
    PEL_regions, PEL_region_count = rg.label_regions(
        illumination_data, valid_map, threshold=PEL_THRESHOLD, greater_than=True
    )

    PSR_region_sizes, _ = rg.region_sizes(PSR_regions)
    PEL_region_sizes, _ = rg.region_sizes(PEL_regions)

    layers = {"illumination": illumination_data, "elevation": elevation_data, "slope": slope_data}
    PSR_region_data = rg.region_data(PSR_regions, PSR_region_count, layers=layers, values={"size": PSR_region_sizes})
    PEL_region_data = rg.region_data(PEL_regions, PEL_region_count, layers=layers, values={"size": PEL_region_sizes})

    filtered_PSR_data, _ = rg.filter_region_data(PSR_region_data, "size", REGION_SIZE_THRESHOLD, greater_than=True)
    filtered_PEL_data, _ = rg.filter_region_data(PEL_region_data, "size", REGION_SIZE_THRESHOLD, greater_than=True)

    print(f"   PSR: {PSR_region_count:,} labelled, {len(filtered_PSR_data):,} above {REGION_SIZE_THRESHOLD} px")
    print(f"   PEL: {PEL_region_count:,} labelled, {len(filtered_PEL_data):,} above {REGION_SIZE_THRESHOLD} px")

    return valid_map, PSR_regions, PEL_regions, filtered_PSR_data, filtered_PEL_data


def run_tier(name, distance, PSR_regions, PEL_regions, viable_PSR, viable_PEL):
    """Pairs, scores and ranks the viable regions at one distance assumption."""

    paired_table = an.pair_tables(viable_PSR, PSR_regions, viable_PEL, PEL_regions,
                                  feasible_distance=distance, pixel_size=PIXEL_SIZE)
    site_table = an.build_site_table(paired_table, viable_PSR, viable_PEL)
    scored_table = an.score_sites(site_table)

    print(f"   {name:14s} <= {distance:6,} m : {len(scored_table):5,} sites, "
          f"{paired_table['PSR_ID'].nunique() if len(paired_table) else 0:4,} PSRs, "
          f"{paired_table['PEL_ID'].nunique() if len(paired_table) else 0:4,} PELs")

    return scored_table


def write_figures(illumination_data, elevation_data, slope_data,
                  PSR_regions, PEL_regions, headline_sites):
    """Writes the layer, region and result figures to the output directory."""

    print("\n== figures ==")
    figure_directory = os.path.join(OUTPUT_DIRECTORY, "figures")
    os.makedirs(figure_directory, exist_ok=True)

    distance_from_PSR = rg.calculate_distance(PSR_regions, PIXEL_SIZE)
    distance_from_PEL = rg.calculate_distance(PEL_regions, PIXEL_SIZE)

    fp.plot_layers(
        data=[elevation_data, illumination_data, slope_data,
              PSR_regions > 0, PEL_regions > 0,
              distance_from_PSR / 1000, distance_from_PEL / 1000],
        title=["Elevation", "Average solar visibility", "Slope",
               f"PSR mask (illumination <= {PSR_THRESHOLD}%)",
               f"PEL mask (illumination > {PEL_THRESHOLD}%)",
               "Distance to nearest PSR", "Distance to nearest PEL"],
        cmap=["terrain", "gray", "viridis", "gray_r", "hot", "magma", "magma"],
        colorbar_label=["Elevation (m)", "Illumination (%)", "Slope (degrees)",
                        "In PSR", "In PEL", "Distance (km)", "Distance (km)"],
        save_path=[os.path.join(figure_directory, f"{n}.png") for n in
                   ["01_elevation", "02_illumination", "03_slope",
                    "04_psr_mask", "05_pel_mask", "06_distance_to_psr", "07_distance_to_pel"]],
        vmax=[None, None, None, None, None, 60, 60],
    )

    # The PEL mask is invisible at full extent: 131 regions of a few dozen pixels each on a
    # 5058 x 5058 grid. A zoom on the pole is the only way to see the result at all.
    half_width = 500
    centre = illumination_data.shape[0] // 2
    window = (slice(centre - half_width, centre + half_width),
              slice(centre - half_width, centre + half_width))

    figure, axis = plt.subplots(figsize=(11, 11))
    axis.imshow(illumination_data[window], cmap="gray", vmin=0, vmax=90)
    axis.imshow(np.ma.masked_where(PSR_regions[window] == 0, PSR_regions[window] > 0),
                cmap="winter", alpha=0.45)
    axis.imshow(np.ma.masked_where(PEL_regions[window] == 0, PEL_regions[window] > 0),
                cmap="autumn", alpha=1.0)
    axis.plot(half_width, half_width, "w+", markersize=16, markeredgewidth=2)
    axis.annotate("south pole", (half_width, half_width), color="white",
                  xytext=(8, 8), textcoords="offset points", fontsize=9)
    axis.set_title(f"Shackleton region, {2 * half_width * PIXEL_SIZE / 1000:.0f} km across\n"
                   "PSRs in blue, PELs in orange, over average solar visibility")
    axis.axis("off")
    figure.savefig(os.path.join(figure_directory, "08_pole_detail.png"), dpi=150, bbox_inches="tight")
    plt.close(figure)
    print(f"   wrote {figure_directory}/08_pole_detail.png")

    # Illumination distribution, and where the two thresholds sit on it.
    figure, axis = plt.subplots(figsize=(10, 6))
    finite = illumination_data[np.isfinite(illumination_data)]
    axis.hist(finite[finite > 0], bins=400, color="#4878a8")
    axis.set_yscale("log")
    axis.axvline(PEL_THRESHOLD, color="#c04040", linestyle="--", label=f"PEL threshold ({PEL_THRESHOLD}%)")
    axis.set_xlabel("Average solar visibility (%)")
    axis.set_ylabel("Pixels (log scale)")
    axis.set_title("Illumination is a continuum, not two populations\n"
                   f"{int((finite == 0).sum()):,} pixels sit at exactly 0% and are excluded from this plot")
    axis.legend()
    figure.savefig(os.path.join(figure_directory, "09_illumination_histogram.png"), dpi=150, bbox_inches="tight")
    plt.close(figure)
    print(f"   wrote {figure_directory}/09_illumination_histogram.png")

    if not headline_sites.empty:
        figure, axis = plt.subplots(figsize=(10, 6))
        top = headline_sites.head(10).iloc[::-1]
        axis.barh(range(len(top)), top["score"], color="#4878a8")
        axis.set_yticks(range(len(top)))
        axis.set_yticklabels(top.index, fontsize=8)
        axis.set_xlabel("Site score")
        axis.set_title(f"Ranked candidate sites, {FEASIBLE_DISTANCE} m walkback limit")
        figure.savefig(os.path.join(figure_directory, "10_ranked_sites.png"), dpi=150, bbox_inches="tight")
        plt.close(figure)
        print(f"   wrote {figure_directory}/10_ranked_sites.png")


def main():
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)
    tables_directory = os.path.join(OUTPUT_DIRECTORY, "tables")
    os.makedirs(tables_directory, exist_ok=True)

    illumination_data, elevation_data, slope_data = build_layers()
    valid_map, PSR_regions, PEL_regions, filtered_PSR_data, filtered_PEL_data = build_regions(
        illumination_data, elevation_data, slope_data
    )

    # Hard constraints first, scoring on the survivors.
    viable_PSR, viable_PEL, constraint_report = an.apply_hard_constraints(
        filtered_PSR_data, filtered_PEL_data,
        max_PEL_slope=MAX_PEL_SLOPE, min_PSR_area=MIN_PSR_AREA, pixel_size=PIXEL_SIZE
    )
    print("\n== hard constraints ==")
    print(f"   PSR area >= {MIN_PSR_AREA} km2 : {constraint_report['PSR_before']:,} -> "
          f"{constraint_report['PSR_after']:,} ({constraint_report['PSR_rejected_area']:,} rejected)")
    print(f"   PEL slope <= {MAX_PEL_SLOPE} deg : {constraint_report['PEL_before']:,} -> "
          f"{constraint_report['PEL_after']:,} ({constraint_report['PEL_rejected_slope']:,} rejected)")

    print("\n== pairing and scoring ==")
    tiers = {name: run_tier(name, distance, PSR_regions, PEL_regions, viable_PSR, viable_PEL)
             for name, distance in DISTANCE_TIERS.items()}
    headline = tiers["walkback_2km"]

    # The unconstrained pairing at the headline distance, kept so the effect of the hard
    # constraints is visible rather than assumed.
    unconstrained_pairs = an.pair_tables(filtered_PSR_data, PSR_regions, filtered_PEL_data, PEL_regions,
                                         feasible_distance=FEASIBLE_DISTANCE, pixel_size=PIXEL_SIZE)

    print("\n== weight sensitivity (headline tier) ==")
    sensitivity = an.weight_sensitivity(headline, top_n=5, draws=2000)
    corners = an.corner_weightings(headline, top_n=5)
    if not sensitivity.empty:
        print(sensitivity.round(3).to_string())
        for factor, sites in corners.items():
            print(f"   {factor:12s} dominant -> {sites[0]}")

    print("\n== validation ==")
    with rasterio.open(ILLUMINATION_RASTER_PATH) as source:
        transform = source.transform

    cold_traps = va.check_known_cold_traps(PSR_regions, transform, pixel_size=PIXEL_SIZE)
    print(cold_traps[["km_from_pole", "nearest_large_PSR_ID", "PSR_area_km2", "km_to_PSR", "passed"]].round(2).to_string())
    print(f"   cold trap check: {int(cold_traps['passed'].sum())}/{len(cold_traps)} located")

    horn = va.horn_slope(elevation_data, PIXEL_SIZE, PIXEL_SIZE)
    slope_comparison = va.compare_slope_algorithms(slope_data, horn, valid_map)
    print(f"   slope vs Horn's method: correlation {slope_comparison['correlation']:.4f}, "
          f"mean |difference| {slope_comparison['mean_absolute_difference']:.3f} deg")

    sanity = va.check_pairing_sanity(unconstrained_pairs)
    for check_name, result in sanity.items():
        print(f"   {check_name}: {'PASS' if result['passed'] else 'FAIL'} ({result['note']})")

    extent = va.psr_extent_summary(PSR_regions, valid_map, PIXEL_SIZE)
    print(f"   PSR extent: {extent['psr_area_km2']:,.0f} km2, "
          f"{100 * extent['shadowed_fraction']:.2f}% of the mapped area")

    print("\n== outputs ==")
    filtered_PSR_data.to_csv(os.path.join(tables_directory, "psr_regions.csv"))
    filtered_PEL_data.to_csv(os.path.join(tables_directory, "pel_regions.csv"))
    unconstrained_pairs.to_csv(os.path.join(tables_directory, "pairs_unconstrained_2km.csv"))
    for name, table in tiers.items():
        table.to_csv(os.path.join(tables_directory, f"sites_{name}.csv"))
    sensitivity.to_csv(os.path.join(tables_directory, "weight_sensitivity.csv"))
    cold_traps.to_csv(os.path.join(tables_directory, "validation_cold_traps.csv"))

    summary = {
        "parameters": {
            "PSR_THRESHOLD": PSR_THRESHOLD, "PEL_THRESHOLD": PEL_THRESHOLD,
            "REGION_SIZE_THRESHOLD": REGION_SIZE_THRESHOLD, "MAX_PEL_SLOPE": MAX_PEL_SLOPE,
            "MIN_PSR_AREA": MIN_PSR_AREA, "PIXEL_SIZE": PIXEL_SIZE,
            "FEASIBLE_DISTANCE": FEASIBLE_DISTANCE, "weights": an.DEFAULT_WEIGHTS,
        },
        "constraints": constraint_report,
        "tiers": {name: {"sites": len(table),
                         "distinct_PSR": int(table["PSR_ID"].nunique()) if len(table) else 0,
                         "distinct_PEL": int(table["PEL_ID"].nunique()) if len(table) else 0,
                         "top_site": table.index[0] if len(table) else None}
                  for name, table in tiers.items()},
        "validation": {
            "cold_traps_located": f"{int(cold_traps['passed'].sum())}/{len(cold_traps)}",
            "slope_comparison": slope_comparison,
            "pairing_sanity": {k: v["passed"] for k, v in sanity.items()},
            "psr_extent": extent,
        },
        "corner_weightings": corners,
    }
    with open(os.path.join(OUTPUT_DIRECTORY, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=2, default=str)
    print(f"   wrote {tables_directory}/ and {OUTPUT_DIRECTORY}/summary.json")

    write_figures(illumination_data, elevation_data, slope_data, PSR_regions, PEL_regions, headline)

    print("\n== top sites, headline tier ==")
    columns = ["PSR_ID", "PEL_ID", "distance", "PEL_illumination", "PEL_slope", "PSR_area_km2", "score"]
    print(headline[columns].head(10).round(2).to_string())


if __name__ == "__main__":
    main()
