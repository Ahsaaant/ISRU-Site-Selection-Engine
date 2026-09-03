import numpy as np, pandas as pd
from scipy import ndimage

# Square metres in one 60 m pixel, used to convert pixel counts to areas.
PIXEL_AREA = 3600.0


def pair_tables(PSR_Table, PSR_Array, PEL_Table, PEL_Array, feasible_distance, pixel_size=60):
    """
    Pairs the PSR and PEL tables based on their region IDs and the distance between them.

    Distance is edge-to-edge: for each PEL region, a Euclidean distance transform gives the
    distance from every pixel to that region's nearest edge, and ndimage.minimum reduces that
    to the closest approach of each PSR.

    The transform is computed inside the PEL region's bounding box grown by the feasible
    distance, not across the whole raster. Any pixel outside that window is further than
    feasible_distance from every pixel of the region by construction, so cropping cannot
    discard a pair that would have qualified.

    Parameters:
    PSR_Table (pd.DataFrame): The table containing PSR region data, indexed by region ID.
    PSR_Array (np.ndarray): The labelled array of PSR regions.
    PEL_Table (pd.DataFrame): The table containing PEL region data, indexed by region ID.
    PEL_Array (np.ndarray): The labelled array of PEL regions.
    feasible_distance (float): The maximum distance in metres between PSR and PEL regions to
        be considered a pair.
    pixel_size (float): The size of each pixel in metres.

    Returns:
    pd.DataFrame: One row per (PEL, PSR, distance) triple, indexed by Pair_ID.
    """

    # Grow each bounding box by the feasible distance, plus one pixel of slack for the
    # half-pixel offsets an edge-to-edge measurement can introduce.
    halo = int(np.ceil(feasible_distance / pixel_size)) + 1
    rows, columns = PEL_Array.shape

    # find_objects returns the bounding box of every label, positionally: index i holds label i+1.
    bounding_boxes = ndimage.find_objects(PEL_Array)

    # Lookup table marking which PSR IDs survived filtering, so windows can be screened cheaply.
    kept_PSR = np.zeros(int(PSR_Array.max()) + 1, dtype=bool)
    kept_PSR[np.asarray(PSR_Table.index)] = True

    pairs = []
    for PEL_region_id in PEL_Table.index:
        box = bounding_boxes[PEL_region_id - 1]
        if box is None:
            continue

        row_start = max(box[0].start - halo, 0)
        row_stop = min(box[0].stop + halo, rows)
        column_start = max(box[1].start - halo, 0)
        column_stop = min(box[1].stop + halo, columns)
        window = (slice(row_start, row_stop), slice(column_start, column_stop))

        # distance_transform_edt measures each True pixel's distance to the nearest False pixel,
        # so the region being measured toward has to be the False one.
        PEL_window = PEL_Array[window]
        distance = ndimage.distance_transform_edt(PEL_window != PEL_region_id, sampling=pixel_size)

        # Only PSRs that both appear in this window and survived filtering can produce a pair.
        PSR_window = PSR_Array[window]
        candidates = np.unique(PSR_window)
        candidates = candidates[candidates > 0]
        candidates = candidates[kept_PSR[candidates]]
        if candidates.size == 0:
            continue

        minimum_distance = np.atleast_1d(
            ndimage.minimum(input=distance, labels=PSR_window, index=candidates)
        )

        within_reach = minimum_distance <= feasible_distance
        for PSR_region_id, dist in zip(candidates[within_reach], minimum_distance[within_reach]):
            pairs.append({
                "Pair_ID": f"PSR_{PSR_region_id} to PEL_{PEL_region_id}",
                "PEL_ID": int(PEL_region_id),
                "PSR_ID": int(PSR_region_id),
                "distance": float(dist),
            })

    # Build the DataFrame from the pairs list. An empty list has no Pair_ID column to index on.
    if pairs:
        paired_table = pd.DataFrame(pairs).set_index("Pair_ID")
    else:
        paired_table = pd.DataFrame(columns=["PEL_ID", "PSR_ID", "distance"])
        print("No pairs found within the feasible distance. Returning an empty DataFrame.")

    return paired_table


def apply_hard_constraints(PSR_Table, PEL_Table, max_PEL_slope, min_PSR_area, pixel_size=60):
    """
    Removes regions that disqualify a site outright, before any scoring happens.

    A PEL too steep to build on and a PSR too small to be worth mining are not poor sites, they
    are not sites. Scoring them low would still let a strong showing on another factor carry
    them up the ranking.

    Parameters:
    PSR_Table (pd.DataFrame): The PSR region table, indexed by region ID.
    PEL_Table (pd.DataFrame): The PEL region table, indexed by region ID.
    max_PEL_slope (float): The maximum mean slope in degrees permitted for a PEL.
    min_PSR_area (float): The minimum area in square kilometres permitted for a PSR.
    pixel_size (float): The size of each pixel in metres.

    Returns:
    pd.DataFrame: The surviving PSR regions.
    pd.DataFrame: The surviving PEL regions.
    dict: Counts before and after, for reporting.
    """

    pixel_area = pixel_size * pixel_size

    PSR_area = PSR_Table["size"] * pixel_area / 1e6
    PEL_area = PEL_Table["size"] * pixel_area / 1e6

    viable_PSR = PSR_Table[PSR_area >= min_PSR_area].copy()
    viable_PEL = PEL_Table[PEL_Table["slope"] <= max_PEL_slope].copy()

    viable_PSR["area_km2"] = PSR_area[viable_PSR.index]
    viable_PEL["area_km2"] = PEL_area[viable_PEL.index]

    report = {
        "PSR_before": len(PSR_Table),
        "PSR_after": len(viable_PSR),
        "PSR_rejected_area": len(PSR_Table) - len(viable_PSR),
        "PEL_before": len(PEL_Table),
        "PEL_after": len(viable_PEL),
        "PEL_rejected_slope": len(PEL_Table) - len(viable_PEL),
        "max_PEL_slope": max_PEL_slope,
        "min_PSR_area": min_PSR_area,
    }

    return viable_PSR, viable_PEL, report


def build_site_table(paired_table, PSR_Table, PEL_Table):
    """
    Joins region properties onto the pairing table by ID.

    The pairing table holds IDs and a distance only; region properties live in the region
    tables. This is the join that brings them together for scoring, and it is the only place
    the two representations are denormalised.

    Parameters:
    paired_table (pd.DataFrame): The long-format pairing table.
    PSR_Table (pd.DataFrame): The PSR region table, indexed by region ID.
    PEL_Table (pd.DataFrame): The PEL region table, indexed by region ID.

    Returns:
    pd.DataFrame: The pairing table with PSR_ and PEL_ prefixed property columns attached.
    """

    if paired_table.empty:
        return paired_table.copy()

    site_table = paired_table.copy()

    PSR_properties = PSR_Table.add_prefix("PSR_")
    PEL_properties = PEL_Table.add_prefix("PEL_")

    site_table = site_table.join(PSR_properties, on="PSR_ID")
    site_table = site_table.join(PEL_properties, on="PEL_ID")

    return site_table


def normalise(values, higher_is_better=True, log_scale=False):
    """
    Rescales a column to 0-1 so that 1 is always the better end.

    The scoring factors carry wildly different units. Distance in metres runs to thousands,
    slope to tens, illumination to 88, area across three orders of magnitude. Without this,
    a weighted sum is just distance with rounding error.

    Parameters:
    values (pd.Series): The column to rescale.
    higher_is_better (bool): False inverts the scale, so lower raw values score higher.
    log_scale (bool): Rescale the base-10 logarithm instead of the raw value. Used for
        strongly skewed columns such as PSR area, where a handful of very large regions
        would otherwise compress everything else into the bottom of the range.

    Returns:
    pd.Series: The rescaled column, in 0-1.
    """

    scaled = np.log10(values) if log_scale else values.astype(float)

    lowest, highest = scaled.min(), scaled.max()
    if highest == lowest:
        # A constant column carries no information; give every row the same neutral value
        # rather than dividing by zero.
        return pd.Series(0.5, index=values.index)

    scaled = (scaled - lowest) / (highest - lowest)

    return scaled if higher_is_better else 1.0 - scaled


DEFAULT_WEIGHTS = {
    "distance": 0.35,       # proximity is the premise of the project
    "illumination": 0.30,   # power availability at the paired PEL
    "area": 0.20,           # PSR size, as a proxy for how much ice could be there
    "slope": 0.15,          # buildability, already partly handled by the hard constraint
}


def score_sites(site_table, weights=None):
    """
    Normalises each scoring factor to 0-1 and combines them into a single weighted score.

    Parameters:
    site_table (pd.DataFrame): The joined site table from build_site_table.
    weights (dict): Weights for distance, illumination, area and slope. Defaults to
        DEFAULT_WEIGHTS. Values are renormalised to sum to 1, so relative size is what matters.

    Returns:
    pd.DataFrame: The site table with normalised factor columns and a score column added,
        sorted by score, highest first.
    """

    if weights is None:
        weights = DEFAULT_WEIGHTS
    if site_table.empty:
        return site_table.copy()

    total_weight = sum(weights.values())
    weights = {name: weight / total_weight for name, weight in weights.items()}

    scored = site_table.copy()

    # Lower is better for distance and slope, so both are inverted. PSR area spans three
    # orders of magnitude and is rescaled on a log axis.
    scored["n_distance"] = normalise(scored["distance"], higher_is_better=False)
    scored["n_illumination"] = normalise(scored["PEL_illumination"], higher_is_better=True)
    scored["n_area"] = normalise(scored["PSR_area_km2"], higher_is_better=True, log_scale=True)
    scored["n_slope"] = normalise(scored["PEL_slope"], higher_is_better=False)

    scored["score"] = (
        weights["distance"] * scored["n_distance"]
        + weights["illumination"] * scored["n_illumination"]
        + weights["area"] * scored["n_area"]
        + weights["slope"] * scored["n_slope"]
    )

    return scored.sort_values("score", ascending=False)


def weight_sensitivity(site_table, top_n=10, draws=2000, seed=0):
    """
    Tests whether the ranking survives a change of weights.

    Draws random weightings from a flat Dirichlet distribution and records how often each site
    lands in the top N. A site that appears under almost every weighting is robust; one that
    only appears under a narrow band of weights is an artefact of the chosen weights, and that
    is a finding in itself rather than a result.

    Parameters:
    site_table (pd.DataFrame): The joined site table from build_site_table.
    top_n (int): The size of the top band to track.
    draws (int): The number of random weightings to test.
    seed (int): Seed for the random generator, so runs are reproducible.

    Returns:
    pd.DataFrame: One row per site that ever reached the top N, with the fraction of
        weightings placing it there, plus its best and median rank.
    """

    if site_table.empty:
        return pd.DataFrame(columns=["top_n_frequency", "best_rank", "median_rank"])

    scored = score_sites(site_table)
    factors = scored[["n_distance", "n_illumination", "n_area", "n_slope"]].to_numpy()

    generator = np.random.default_rng(seed)
    random_weights = generator.dirichlet(np.ones(4), size=draws)

    # (draws x 4) against (4 x sites) gives every site's score under every weighting at once.
    all_scores = random_weights @ factors.T

    # argsort descending, then invert the permutation to turn positions into ranks.
    order = np.argsort(-all_scores, axis=1)
    ranks = np.empty_like(order)
    np.put_along_axis(ranks, order, np.arange(1, all_scores.shape[1] + 1), axis=1)

    in_top = ranks <= top_n
    ever_top = in_top.any(axis=0)

    summary = pd.DataFrame({
        "top_n_frequency": in_top.mean(axis=0)[ever_top],
        "best_rank": ranks.min(axis=0)[ever_top],
        "median_rank": np.median(ranks, axis=0)[ever_top],
    }, index=scored.index[ever_top])

    return summary.sort_values("top_n_frequency", ascending=False)


def corner_weightings(site_table, dominant=0.7, top_n=10):
    """
    Scores the table once per factor with that factor dominant, as a readable companion to the
    random sweep. If the same sites top all four corners, the ranking does not depend on the
    weighting at all.

    Parameters:
    site_table (pd.DataFrame): The joined site table from build_site_table.
    dominant (float): The weight given to the dominant factor; the rest is split evenly.
    top_n (int): How many rows of each corner ranking to return.

    Returns:
    dict: Factor name mapped to that corner's top N site IDs.
    """

    factors = ["distance", "illumination", "area", "slope"]
    others = (1.0 - dominant) / (len(factors) - 1)

    corners = {}
    for factor in factors:
        weights = {name: (dominant if name == factor else others) for name in factors}
        corners[factor] = list(score_sites(site_table, weights).index[:top_n])

    return corners


# Test functions
if __name__ == "__main__":
    # A four by four grid with two PSRs and two PELs, small enough to check the distances by hand.
    Example_PSR_Table = pd.DataFrame({
        "region_id": [1, 2, 3],
        "illumination": [0.0, 0.0, 0.0],
        "elevation": [100, 200, 300],
        "slope": [5, 10, 15],
        "size": [400, 900, 150],
    }).set_index("region_id")

    Example_PSR_Array = np.array([[1, 1, 0, 3],
                                  [1, 1, 3, 0],
                                  [0, 0, 2, 2],
                                  [0, 0, 2, 2]])

    Example_PEL_Table = pd.DataFrame({
        "region_id": [1, 2],
        "illumination": [60.0, 70.0],
        "elevation": [400, 500],
        "slope": [20, 8],
        "size": [200, 250],
    }).set_index("region_id")

    Example_PEL_Array = np.array([[0, 0, 1, 1],
                                  [0, 0, 1, 1],
                                  [2, 2, 0, 0],
                                  [2, 2, 0, 0]])

    pairs = pair_tables(Example_PSR_Table, Example_PSR_Array,
                        Example_PEL_Table, Example_PEL_Array,
                        feasible_distance=200, pixel_size=60)
    print("Pairs:\n", pairs)

    viable_PSR, viable_PEL, report = apply_hard_constraints(
        Example_PSR_Table, Example_PEL_Table, max_PEL_slope=15, min_PSR_area=1.0
    )
    print("\nHard constraint report:", report)
    print("Surviving PSRs:", list(viable_PSR.index), " surviving PELs:", list(viable_PEL.index))

    # Score the unconstrained pairing, so the example still has rows to rank.
    viable_PSR = Example_PSR_Table.assign(area_km2=Example_PSR_Table["size"] * PIXEL_AREA / 1e6)
    viable_PEL = Example_PEL_Table.assign(area_km2=Example_PEL_Table["size"] * PIXEL_AREA / 1e6)
    sites = build_site_table(pairs, viable_PSR, viable_PEL)
    print("\nScored sites:\n", score_sites(sites)[["PSR_ID", "PEL_ID", "distance", "score"]])
    print("\nCorner weightings:", corner_weightings(sites, top_n=2))
