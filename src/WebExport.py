"""
Phase 5: precomputes the engine's results for every configuration the website offers and writes
them, along with the basemap tiles, into docs/ for the static site.

Run from the project root, like Main.py:
    python src/WebExport.py
"""
import base64, contextlib, io, json, math, os, shutil
from datetime import date

import numpy as np, pandas as pd, rasterio
from PIL import Image
from rasterio.crs import CRS
from rasterio.warp import transform as warp_transform
from scipy import ndimage

import FileProcessing as fp
import Regions as rg
import Analysis as an
from Main import (ALTITUDE_RASTER_PATH, ILLUMINATION_RASTER_PATH, PSR_THRESHOLD, PEL_THRESHOLD,
                  REGION_SIZE_THRESHOLD, FEASIBLE_DISTANCE, SLOPE_THRESHOLD, PIXEL_SIZE)

SITE_DIR = "docs"

# The options the website offers. Every combination is precomputed, so the site never runs the engine.
PEL_THRESHOLDS = [50, 55, 60, 65]
FEASIBLE_DISTANCES = [1000, 2000, 3000, 5000]
WEIGHT_PRESETS = {
    "balanced": {"label": "Balanced", "distance": 1, "illumination": 1, "size": 1},
    "power": {"label": "Power first", "distance": 1, "illumination": 3, "size": 1},
    "traverse": {"label": "Short traverse", "distance": 3, "illumination": 1, "size": 1},
    "ice": {"label": "Largest cold trap", "distance": 1, "illumination": 1, "size": 3},
}

TOP_N_SITES = 3
LATITUDE_RINGS = [89, 88, 87, 86, 85]
TILE_SIZE = 256

# Overlay colours, matching the score segments on the site (PSR -> size, PEL -> illumination)
PSR_COLOUR = (57, 135, 229)
PEL_COLOUR = (217, 89, 38)


def load_layers():
    """
    Loads and prepares the layers exactly as Main.py does.

    Returns:
    tuple of numpy.ndarray: The illumination, elevation, slope, and validity layers.
    """

    illumination_data, illumination_scale_factor = fp.read_raster(ILLUMINATION_RASTER_PATH)
    resampled_altitude_data, pixel_size_x, pixel_size_y = fp.resample_raster(ALTITUDE_RASTER_PATH, ILLUMINATION_RASTER_PATH)
    elevation_data = fp.radius_to_elevation(resampled_altitude_data)
    illumination = fp.scale_illumination_data(illumination_data, illumination_scale_factor)
    slope_data = fp.elevation_to_slope(elevation_data, pixel_size_x=pixel_size_x, pixel_size_y=pixel_size_y)
    valid_map = rg.validate_layers([illumination, elevation_data, slope_data])

    return illumination, elevation_data, slope_data, valid_map


def filtered_regions(layers, threshold, greater_than, prefix):
    """
    Labels and filters the PSR or PEL regions exactly as Main.py does.

    Parameters:
    layers (tuple): The output of load_layers.
    threshold (float): The illumination threshold for the regions.
    greater_than (bool): True for PELs, False for PSRs.
    prefix (str): "PSR_" or "PEL_".

    Returns:
    numpy.ndarray: The labelled regions.
    pandas.DataFrame: The regions that pass the size and slope filters.
    """

    illumination, elevation_data, slope_data, valid_map = layers
    labels, region_count = rg.label_regions(illumination, valid_map, threshold=threshold, greater_than=greater_than)
    sizes, _ = rg.region_sizes(labels)
    table = rg.region_data(labels, region_count, layers={"illumination": illumination, "elevation": elevation_data, "slope": slope_data}, values={"size": sizes})
    table, _ = rg.filter_region_data(table, "size", REGION_SIZE_THRESHOLD, greater_than=True, PSR_or_PEL=prefix)
    table, _ = rg.filter_region_data(table, f"{prefix}slope", SLOPE_THRESHOLD, greater_than=False)

    return labels, table


def window_around(box, margin):
    """Pads a region's bounding box by margin pixels; numpy clips the far edges to the raster."""

    rows, cols = box
    return slice(max(rows.start - margin, 0), rows.stop + margin), slice(max(cols.start - margin, 0), cols.stop + margin)


def pair_regions(PSR_labels, PSR_table, PEL_labels, PEL_table, PEL_boxes, feasible_distance):
    """
    Runs Analysis.pair_tables one PEL at a time, on a window that reaches feasible_distance past
    the PEL in every direction. Every PSR pixel close enough to pair is inside the window, so the
    pairs and distances match a full-raster run, without a full-raster distance transform per PEL.

    Returns:
    pandas.DataFrame: The pairs within feasible_distance, as returned by pair_tables.
    """

    margin = math.ceil(feasible_distance / PIXEL_SIZE) + 1
    tables = []

    for PEL_id in PEL_table.index:
        window = window_around(PEL_boxes[PEL_id - 1], margin)
        PSR_window = PSR_labels[window]
        nearby_PSRs = PSR_table[PSR_table.index.isin(np.unique(PSR_window))]
        if nearby_PSRs.empty:
            continue

        # pair_tables prints a notice for every PEL without a pair, which would flood the output
        with contextlib.redirect_stdout(io.StringIO()):
            pairs = an.pair_tables(nearby_PSRs, PSR_window, PEL_table.loc[[PEL_id]], PEL_labels[window], feasible_distance=feasible_distance, pixel_size=PIXEL_SIZE)
        if not pairs.empty:
            tables.append(pairs)

    return pd.concat(tables) if tables else pd.DataFrame()


def closest_points(PSR_labels, PSR_id, PEL_labels, PEL_id, PEL_box, margin):
    """
    Finds the PSR pixel closest to the PEL, and the PEL pixel it is closest to, as Display.map_pairs does.

    Returns:
    tuple: (row, col) of the PSR pixel and (row, col) of the PEL pixel, in full-raster coordinates.
    """

    rows, cols = window_around(PEL_box, margin)
    distance, (nearest_row, nearest_col) = ndimage.distance_transform_edt(PEL_labels[rows, cols] != PEL_id, return_indices=True)  # type: ignore

    PSR_rows, PSR_cols = np.nonzero(PSR_labels[rows, cols] == PSR_id)
    closest = np.argmin(distance[PSR_rows, PSR_cols])
    PSR_row, PSR_col = PSR_rows[closest], PSR_cols[closest]

    return ((PSR_row + rows.start, PSR_col + cols.start),
            (nearest_row[PSR_row, PSR_col] + rows.start, nearest_col[PSR_row, PSR_col] + cols.start))


def geographic_crs(projected_crs):
    """Extracts the GEOGCS block of the raster's projected CRS, so points can be converted to latitude and longitude."""

    wkt = projected_crs.to_wkt()
    start, depth = wkt.index("GEOGCS["), 0
    for end in range(start, len(wkt)):
        depth += {"[": 1, "]": -1}.get(wkt[end], 0)
        if wkt[end] == "]" and depth == 0:
            return CRS.from_wkt(wkt[start:end + 1])


def region_overlay(labels, box, region_id, colour, transform):
    """
    Cuts a region out of its label array as a coloured, transparent PNG.

    Returns:
    dict: The PNG as a data URI and its bounds in projected metres as [[south, west], [north, east]].
    """

    rows, cols = box
    mask = labels[rows, cols] == region_id
    rgba = np.zeros(mask.shape + (4,), dtype=np.uint8)
    rgba[mask] = (*colour, 255)

    buffer = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buffer, format="PNG", optimize=True)

    west, north = transform * (cols.start, rows.start)
    east, south = transform * (cols.stop, rows.stop)
    return {"png": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode(),
            "bounds": [[south, west], [north, east]]}


def write_tiles(illumination, elevation_data):
    """
    Renders the basemap and cuts it into a zoomable tile pyramid at docs/tiles/{z}/{x}/{y}.webp.
    Brightness is the sunlight visibility; a faint hillshade keeps the terrain readable inside
    the permanently shadowed craters, which would otherwise be flat black.

    Returns:
    int: The zoom level at which one tile pixel is one raster pixel.
    """

    # Hillshade with the light from the top left of the map
    grad_x, grad_y = np.gradient(elevation_data, PIXEL_SIZE)
    slope = np.pi / 2 - np.arctan(np.hypot(grad_x, grad_y))
    aspect = np.arctan2(-grad_x, grad_y)
    azimuth, altitude = np.radians(315), np.radians(45)
    hillshade = np.sin(altitude) * np.sin(slope) + np.cos(altitude) * np.cos(slope) * np.cos(azimuth - aspect)

    sunlight = np.clip(illumination / np.nanmax(illumination), 0, 1)
    shade = np.clip(hillshade, 0, 1)
    basemap = np.nan_to_num(sunlight * 205 + shade * 50, nan=0).astype(np.uint8)
    image = Image.fromarray(basemap, "L")

    tile_dir = os.path.join(SITE_DIR, "tiles")
    shutil.rmtree(tile_dir, ignore_errors=True)

    max_zoom = math.ceil(math.log2(max(image.size) / TILE_SIZE))
    for zoom in range(max_zoom + 1):
        scale = 2 ** (max_zoom - zoom)
        level = image.resize((math.ceil(image.width / scale), math.ceil(image.height / scale)), Image.Resampling.LANCZOS)

        for x in range(math.ceil(level.width / TILE_SIZE)):
            os.makedirs(os.path.join(tile_dir, str(zoom), str(x)), exist_ok=True)
            for y in range(math.ceil(level.height / TILE_SIZE)):
                # Tiles past the raster edge are padded with black, which matches the map background
                tile = level.crop((x * TILE_SIZE, y * TILE_SIZE, (x + 1) * TILE_SIZE, (y + 1) * TILE_SIZE))
                tile.save(os.path.join(tile_dir, str(zoom), str(x), f"{y}.webp"), quality=72, method=6)

    return max_zoom


def main():
    layers = load_layers()
    illumination, elevation_data, _, _ = layers

    with rasterio.open(ILLUMINATION_RASTER_PATH) as source:
        transform, crs, width, height = source.transform, source.crs, source.width, source.height
    lunar_crs = geographic_crs(crs)

    def projected(row, col):
        """Pixel centre in projected metres from the pole."""
        x, y = transform * (col + 0.5, row + 0.5)
        return [round(x, 1), round(y, 1)]

    PSR_labels, PSR_table = filtered_regions(layers, PSR_THRESHOLD, greater_than=False, prefix="PSR_")
    PSR_boxes = ndimage.find_objects(PSR_labels)
    margin = math.ceil(max(FEASIBLE_DISTANCES) / PIXEL_SIZE) + 1
    print(f"{len(PSR_table)} PSRs pass the filters")

    configs, overlays, PEL_counts, PSR_ranks = {}, {}, {}, {}
    for threshold in PEL_THRESHOLDS:
        PEL_labels, PEL_table = filtered_regions(layers, threshold, greater_than=True, prefix="PEL_")
        PEL_boxes = ndimage.find_objects(PEL_labels)
        PEL_counts[threshold] = len(PEL_table)

        # Pair once at the longest distance, then cut down for the shorter ones
        all_pairs = pair_regions(PSR_labels, PSR_table, PEL_labels, PEL_table, PEL_boxes, max(FEASIBLE_DISTANCES))
        print(f"PEL threshold {threshold}%: {len(PEL_table)} PELs, {len(all_pairs)} pairs within {max(FEASIBLE_DISTANCES)} m")

        for distance in FEASIBLE_DISTANCES:
            pairs = all_pairs[all_pairs["distance"] <= distance] if len(all_pairs) else all_pairs

            for preset_key, preset in WEIGHT_PRESETS.items():
                total_weight = preset["distance"] + preset["illumination"] + preset["size"]
                scored = an.score_pairs(pairs.copy(), distance_weight=preset["distance"], illumination_weight=preset["illumination"],
                                        size_weight=preset["size"], illumination_threshold=threshold, feasible_distance=distance) if len(pairs) else pairs
                config_key = f"{threshold}|{distance}|{preset_key}"

                # Each PSR's rank by its best pair. PSR labels are the same in every configuration, while PEL
                # labels change with the threshold, so the site follows a PSR to show how robust it is.
                PSR_order = pairs.loc[scored.index, "PSR_ID"].astype(int).reset_index(drop=True).drop_duplicates() if len(pairs) else pd.Series(dtype=int)
                PSR_ranks[config_key] = dict(zip(PSR_order.tolist(), (PSR_order.index + 1).tolist()))

                sites = []
                for pair_id, row in scored.head(TOP_N_SITES).iterrows():
                    PSR_id, PEL_id = int(pairs.loc[pair_id, "PSR_ID"]), int(pairs.loc[pair_id, "PEL_ID"])
                    PSR_point, PEL_point = closest_points(PSR_labels, PSR_id, PEL_labels, PEL_id, PEL_boxes[PEL_id - 1], margin)
                    mid_row, mid_col = (PSR_point[0] + PEL_point[0]) / 2, (PSR_point[1] + PEL_point[1]) / 2

                    mid = projected(mid_row, mid_col)
                    (lon,), (lat,) = warp_transform(crs, lunar_crs, [mid[0]], [mid[1]])

                    PSR_key, PEL_key = f"psr-{PSR_id}", f"pel-{threshold}-{PEL_id}"
                    if PSR_key not in overlays:
                        overlays[PSR_key] = region_overlay(PSR_labels, PSR_boxes[PSR_id - 1], PSR_id, PSR_COLOUR, transform)
                    if PEL_key not in overlays:
                        overlays[PEL_key] = region_overlay(PEL_labels, PEL_boxes[PEL_id - 1], PEL_id, PEL_COLOUR, transform)

                    sites.append({
                        "pair": pair_id, "psr": PSR_id, "pel": PEL_id,
                        "distance_m": round(float(row["distance"]), 1),
                        "pel_illumination": round(float(row["PEL_illumination"]), 1),
                        "psr_area_km2": round(float(row["PSR_size"]) * PIXEL_SIZE ** 2 / 1e6, 3),
                        "total": round(float(row["total_score"]), 4),
                        # Each criterion's share of the total score, so the three add up to it
                        "parts": {criterion: round(float(row[f"{criterion}_score"]) / total_weight, 4) for criterion in ["distance", "illumination", "size"]},
                        "psr_point": projected(*PSR_point), "pel_point": projected(*PEL_point), "mid": mid,
                        "lat": round(lat, 3), "lon": round(lon % 360, 2),
                        "overlays": [PSR_key, PEL_key],
                    })

                configs[config_key] = {"pairs": len(pairs), "sites": sites}

    # Only the PSRs that appear in a top 3 are shown on the site, so only theirs are kept
    shown_PSRs = {site["psr"] for config in configs.values() for site in config["sites"]}
    for config_key, config in configs.items():
        config["ranks"] = {PSR_id: rank for PSR_id, rank in PSR_ranks[config_key].items() if PSR_id in shown_PSRs}

    # Radius of each latitude ring around the pole, for the map's graticule
    xs, ys = warp_transform(lunar_crs, crs, [0.0] * len(LATITUDE_RINGS), [-lat for lat in LATITUDE_RINGS])
    rings = [{"lat": lat, "radius": round(math.hypot(x, y), 1)} for lat, x, y in zip(LATITUDE_RINGS, xs, ys)]

    tile_zoom = write_tiles(illumination, elevation_data)

    data = {
        "generated": date.today().isoformat(),
        "raster": {"west": transform.c, "north": transform.f, "pixelSize": PIXEL_SIZE, "width": width, "height": height,
                   "tileZoom": tile_zoom, "tileSize": TILE_SIZE},
        "rings": rings,
        "options": {"pel": PEL_THRESHOLDS, "distance": FEASIBLE_DISTANCES, "weights": WEIGHT_PRESETS},
        "defaults": {"pel": PEL_THRESHOLD, "distance": FEASIBLE_DISTANCE, "weights": "balanced"},
        "counts": {"psr": len(PSR_table), "pel": PEL_counts},
        "configs": configs,
        "overlays": overlays,
    }

    # A script rather than JSON, so the site also works when index.html is opened straight from disk
    os.makedirs(os.path.join(SITE_DIR, "data"), exist_ok=True)
    with open(os.path.join(SITE_DIR, "data", "results.js"), "w") as file:
        file.write("window.ENGINE_DATA = " + json.dumps(data, separators=(",", ":")) + ";\n")
    open(os.path.join(SITE_DIR, ".nojekyll"), "w").close()

    print(f"Wrote {len(configs)} configurations and {len(overlays)} region overlays to {SITE_DIR}/")


if __name__ == "__main__":
    main()
