import numpy as np, pandas as pd
from scipy import ndimage

# LOLA reference sphere radius, in metres. The same value the elevation conversion uses.
MOON_RADIUS = 1737400.0

# Named south polar craters, as (latitude, east longitude) in degrees. Every one of these is a
# well documented cold trap, so each should land inside a large PSR if the mask is correct.
# Shackleton is the ground truth CLAUDE.md calls for: the literature places peaks of
# near-eternal light on its rim, so it should also carry a high ranking pair.
KNOWN_COLD_TRAPS = {
    "Shackleton": (-89.90, 0.0),
    "de Gerlache": (-88.50, 273.0),
    "Shoemaker": (-88.10, 44.9),
    "Haworth": (-87.50, 355.0),
    "Faustini": (-87.30, 77.0),
    "Sverdrup": (-88.30, 208.0),
}


def horn_slope(elevation_data, pixel_size_x, pixel_size_y):
    """
    Calculates slope using Horn's method, the third-order finite difference algorithm that
    GDAL and QGIS's Raster > Analysis > Slope both use.

    This exists to check the pipeline's np.gradient slope against an independent algorithm.
    np.gradient uses a two-point central difference along each axis in isolation; Horn takes a
    weighted average over all eight neighbours, which is less sensitive to single-pixel noise.
    Agreement between the two is evidence the slope layer is not simply wrong.

    Parameters:
    elevation_data (numpy.ndarray): The elevation data in metres.
    pixel_size_x (float): The pixel size along the x-axis in metres.
    pixel_size_y (float): The pixel size along the y-axis in metres.

    Returns:
    numpy.ndarray: The slope in degrees, with a one pixel NaN border where the 3x3 window
        does not fit.
    """

    # Pad with NaN so the eight neighbour windows line up with the original shape and the
    # border comes out as NaN rather than wrapping or repeating.
    padded = np.pad(elevation_data.astype(np.float64), 1, mode="constant", constant_values=np.nan)

    a, b, c = padded[:-2, :-2], padded[:-2, 1:-1], padded[:-2, 2:]
    d, f = padded[1:-1, :-2], padded[1:-1, 2:]
    g, h, i = padded[2:, :-2], padded[2:, 1:-1], padded[2:, 2:]

    dz_dx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * pixel_size_x)
    dz_dy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * pixel_size_y)

    return np.degrees(np.arctan(np.sqrt(dz_dx ** 2 + dz_dy ** 2)))


def compare_slope_algorithms(gradient_slope, reference_slope, valid_mask=None):
    """
    Quantifies agreement between the pipeline's slope layer and an independent one.

    Parameters:
    gradient_slope (numpy.ndarray): The pipeline's np.gradient slope, in degrees.
    reference_slope (numpy.ndarray): The Horn slope, in degrees.
    valid_mask (numpy.ndarray): Optional boolean mask limiting the comparison.

    Returns:
    dict: Agreement statistics.
    """

    comparable = ~np.isnan(gradient_slope) & ~np.isnan(reference_slope)
    if valid_mask is not None:
        comparable &= valid_mask

    left = gradient_slope[comparable].astype(np.float64)
    right = reference_slope[comparable].astype(np.float64)
    difference = left - right

    return {
        "pixels_compared": int(comparable.sum()),
        "gradient_mean": float(left.mean()),
        "horn_mean": float(right.mean()),
        "gradient_max": float(left.max()),
        "horn_max": float(right.max()),
        "mean_absolute_difference": float(np.abs(difference).mean()),
        "median_absolute_difference": float(np.median(np.abs(difference))),
        "p95_absolute_difference": float(np.percentile(np.abs(difference), 95)),
        "max_absolute_difference": float(np.abs(difference).max()),
        "correlation": float(np.corrcoef(left, right)[0, 1]),
    }


def latlon_to_pixel(latitude, longitude, transform, radius=MOON_RADIUS):
    """
    Converts a lunar latitude and east longitude to a row and column in the south polar
    stereographic grid the analysis runs on.

    The projection is spherical polar stereographic with its origin at the south pole and true
    scale at the pole, so the distance from the pole is 2 R tan(45 degrees - |lat| / 2). At 85
    degrees south that gives 151,700 m, which matches the raster's 151,740 m half-width; that
    agreement is what confirms the formula against this particular grid.

    Parameters:
    latitude (float): Latitude in degrees, negative in the southern hemisphere.
    longitude (float): East longitude in degrees.
    transform (affine.Affine): The raster's affine transform.
    radius (float): The reference sphere radius in metres.

    Returns:
    tuple: The (row, column) pixel indices, as integers.
    """

    polar_distance = 2 * radius * np.tan(np.radians(45 + latitude / 2))
    longitude_radians = np.radians(longitude)

    x = polar_distance * np.sin(longitude_radians)
    y = polar_distance * np.cos(longitude_radians)

    column = (x - transform.c) / transform.a
    row = (y - transform.f) / transform.e

    return int(round(row)), int(round(column))


def check_known_cold_traps(PSR_Array, transform, pixel_size=60, craters=None, search_radius=8000):
    """
    Checks that each named crater sits in or beside a labelled PSR of a plausible size.

    A derived mask that is mirrored, rotated, or sitting on the wrong pole will still look
    reasonable in isolation. Landing six independently documented craters on six large
    shadowed regions is the check that catches that class of error.

    The test is proximity rather than a strict point hit, because catalogued crater centres
    carry limited precision and, very close to the pole, almost no positional information at
    all: Shackleton's cited centre is 3 km from the pole, where a fraction of a degree of
    longitude swings the point right across the crater. A point test would fail there for a
    reason that has nothing to do with the mask being wrong.

    Parameters:
    PSR_Array (numpy.ndarray): The labelled PSR array.
    transform (affine.Affine): The raster's affine transform.
    pixel_size (float): The pixel size in metres.
    craters (dict): Name mapped to (latitude, east longitude). Defaults to KNOWN_COLD_TRAPS.
    search_radius (float): How far in metres to look for a large PSR around each point.

    Returns:
    pd.DataFrame: One row per crater with its pixel location, the largest PSR found nearby,
        that region's area, and how far the catalogued point sits from it.
    """

    if craters is None:
        craters = KNOWN_COLD_TRAPS

    rows, columns = PSR_Array.shape
    centre_row, centre_column = (rows - 1) / 2, (columns - 1) / 2
    pixel_area = pixel_size * pixel_size
    areas = np.bincount(PSR_Array.ravel()) * pixel_area / 1e6

    radius_pixels = int(round(search_radius / pixel_size))

    results = []
    for name, (latitude, longitude) in craters.items():
        row, column = latlon_to_pixel(latitude, longitude, transform)
        on_grid = 0 <= row < rows and 0 <= column < columns

        record = {
            "latitude": latitude,
            "east_longitude": longitude,
            "row": row,
            "column": column,
            "km_from_pole": float(np.hypot(row - centre_row, column - centre_column) * pixel_size / 1000),
            "point_PSR_ID": int(PSR_Array[row, column]) if on_grid else 0,
            "nearest_large_PSR_ID": 0,
            "PSR_area_km2": 0.0,
            "km_to_PSR": np.nan,
            "passed": False,
        }

        if on_grid:
            window = PSR_Array[max(row - radius_pixels, 0):row + radius_pixels,
                               max(column - radius_pixels, 0):column + radius_pixels]
            nearby = np.unique(window[window > 0])
            if nearby.size:
                # The biggest shadowed region in the neighbourhood is the crater floor; small
                # neighbouring speckle should not be what the crater is matched against.
                largest = int(nearby[np.argmax(areas[nearby])])
                region_rows, region_columns = np.nonzero(PSR_Array == largest)
                distance = float(np.hypot(region_rows - row, region_columns - column).min() * pixel_size / 1000)
                record.update({
                    "nearest_large_PSR_ID": largest,
                    "PSR_area_km2": float(areas[largest]),
                    "km_to_PSR": distance,
                    "passed": bool(areas[largest] >= 10.0 and distance <= search_radius / 1000),
                })

        results.append({"crater": name, **record})

    return pd.DataFrame(results).set_index("crater")


def check_pairing_sanity(paired_table, expected_minimum=5, expected_maximum=10000):
    """
    Runs the checks CLAUDE.md requires the first time the pairing table meets real data.

    A PSR that appears beside several PELs must show a different distance to each. Identical
    distances would mean the per-PEL mask is not being rebuilt inside the loop, which is the
    single most likely way for the pairing to be silently wrong.

    Parameters:
    paired_table (pd.DataFrame): The pairing table.
    expected_minimum (int): Below this many rows, the result is treated as suspicious.
    expected_maximum (int): Above this many rows, the result is treated as suspicious.

    Returns:
    dict: The check results, each with a pass or fail verdict.
    """

    checks = {}
    row_count = len(paired_table)

    checks["row_count"] = {
        "value": row_count,
        "passed": expected_minimum <= row_count <= expected_maximum,
        "note": f"expected between {expected_minimum} and {expected_maximum} rows",
    }

    if row_count == 0:
        checks["distinct_distances"] = {"value": None, "passed": False, "note": "no pairs to check"}
        return checks

    # The failure CLAUDE.md describes is the per-PEL mask never being rebuilt inside the loop,
    # which would give a PSR the *same* distance to every PEL it pairs with. That is the
    # condition tested here.
    #
    # Individual ties are not evidence of it. A Euclidean distance transform on a regular grid
    # returns 60 * sqrt(integer), so two genuinely different PELs landing on the same value is
    # ordinary quantisation and is reported separately as information, not as a failure.
    repeated = paired_table.groupby("PSR_ID").filter(lambda group: len(group) > 1)
    if len(repeated) == 0:
        checks["distinct_distances"] = {
            "value": 0, "passed": True, "note": "no PSR pairs with more than one PEL; check not applicable",
        }
    else:
        distinct_counts = repeated.groupby("PSR_ID")["distance"].nunique()
        group_sizes = repeated.groupby("PSR_ID")["distance"].size()
        all_identical = int((distinct_counts == 1).sum())
        has_a_tie = int((distinct_counts < group_sizes).sum())
        checks["distinct_distances"] = {
            "value": all_identical,
            "passed": all_identical == 0,
            "note": f"{len(distinct_counts)} PSRs pair with multiple PELs; {all_identical} show a "
                    f"single repeated distance across all their PELs ({has_a_tie} contain a tie, "
                    f"which is expected quantisation)",
        }

    checks["distance_within_bounds"] = {
        "value": float(paired_table["distance"].max()),
        "passed": bool(paired_table["distance"].min() >= 0),
        "note": "all distances must be non-negative",
    }

    return checks


def psr_extent_summary(PSR_Array, valid_mask, pixel_size=60):
    """
    Summarises the derived PSR mask's total extent, for comparison against published figures.

    The published LOLA LPSR product is the intended comparison and is not held locally, so this
    reports the derived extent in the units the literature uses and leaves the comparison to
    the write-up.

    Parameters:
    PSR_Array (numpy.ndarray): The labelled PSR array.
    valid_mask (numpy.ndarray): The validity mask.
    pixel_size (float): The pixel size in metres.

    Returns:
    dict: Areas and fractions.
    """

    pixel_area = pixel_size * pixel_size
    shadowed = int((PSR_Array > 0).sum())
    valid = int(valid_mask.sum())

    return {
        "psr_pixels": shadowed,
        "psr_area_km2": shadowed * pixel_area / 1e6,
        "valid_pixels": valid,
        "valid_area_km2": valid * pixel_area / 1e6,
        "shadowed_fraction": shadowed / valid if valid else 0.0,
    }


# Test functions
if __name__ == "__main__":
    from affine import Affine

    # A cone, so the slope is known analytically: a constant gradient of 1 in 10 is 5.71 degrees.
    size = 101
    y, x = np.mgrid[:size, :size]
    cone = np.hypot(y - size // 2, x - size // 2) * 6.0  # 6 m rise per 60 m pixel

    horn = horn_slope(cone, 60, 60)
    print(f"Horn slope on a 1-in-10 cone: {np.nanmedian(horn):.3f} degrees (expected 5.711)")

    gradient_y, gradient_x = np.gradient(cone, 60.0, 60.0)
    gradient_slope = np.degrees(np.arctan(np.hypot(gradient_x, gradient_y)))
    print("Comparison:", compare_slope_algorithms(gradient_slope, horn))

    # 85 degrees south should land on the edge of a 5058 pixel grid of 60 m pixels.
    transform = Affine(60.0, 0.0, -151740.0, 0.0, -60.0, 151740.0)
    print("\nPole ->", latlon_to_pixel(-90.0, 0.0, transform), "(expected near (2529, 2529))")
    print("85S at 0E ->", latlon_to_pixel(-85.0, 0.0, transform), "(expected near the top edge)")
    print("85S at 90E ->", latlon_to_pixel(-85.0, 90.0, transform), "(expected near the right edge)")

    example_pairs = pd.DataFrame({
        "PEL_ID": [1, 2, 1, 2],
        "PSR_ID": [1, 1, 2, 2],
        "distance": [100.0, 250.0, 300.0, 300.0],
    })
    print("\nSanity checks on example pairs:")
    for name, result in check_pairing_sanity(example_pairs, expected_minimum=1).items():
        print(f"  {name}: {'PASS' if result['passed'] else 'FAIL'} - {result['note']}")
