// Interactive results for the ISRU Site-Selection Engine. Every configuration is precomputed by
// src/WebExport.py into data/results.js, so changing a setting is a lookup rather than a run.
(function () {
  "use strict";

  const DATA = window.ENGINE_DATA;
  const REFERENCE = window.REFERENCE_SITES; // Wueller et al. (2026)'s landing sites, from data/reference.js
  const RASTER = DATA.raster;
  const OPTIONS = DATA.options;
  const DEFAULTS = DATA.defaults;

  const MOON_RADIUS = 1737400; // LOLA reference sphere radius in metres, as in FileProcessing.py
  const PIN_SPACING = 32; // Pins closer than this on screen are spread apart, in pixels
  const CRITERIA = [
    { key: "distance", label: "Distance" },
    { key: "illumination", label: "Illumination" },
    { key: "size", label: "Size" },
  ];
  const TOP_SITES = 3;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const integer = new Intl.NumberFormat("en-US");

  const $ = (id) => document.getElementById(id);
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const toLatLng = ([x, y]) => L.latLng(y, x); // The map's "latitude" is projected northing in metres

  let state = readHash();
  let siteLayers = [];

  /* ---------- Configuration state, kept in the URL so a view can be shared ---------- */

  function readHash() {
    const params = new URLSearchParams(location.hash.slice(1));
    const pel = Number(params.get("pel"));
    const distance = Number(params.get("distance"));
    const weights = params.get("weights");
    return {
      pel: OPTIONS.pel.includes(pel) ? pel : DEFAULTS.pel,
      distance: OPTIONS.distance.includes(distance) ? distance : DEFAULTS.distance,
      weights: Object.hasOwn(OPTIONS.weights, weights) ? weights : DEFAULTS.weights,
    };
  }

  function writeHash() {
    const hash = "#" + new URLSearchParams({ pel: state.pel, distance: state.distance, weights: state.weights });
    try {
      history.replaceState(null, "", hash);
    } catch (error) {
      // Some browsers block history changes on pages opened from disk; the page works without it
    }
  }

  /* ---------- Formatting ---------- */

  function kilometres(metres) {
    return `${metres / 1000} km`;
  }

  function area(km2) {
    return `${km2 < 0.1 ? km2.toFixed(3) : km2.toFixed(2)} km²`;
  }

  function toLatLon(x, y) {
    const rho = Math.hypot(x, y);
    const colatitude = 2 * Math.atan(rho / (2 * MOON_RADIUS)); // Inverse of the polar stereographic projection
    return {
      lat: -(90 - (colatitude * 180) / Math.PI),
      lon: ((Math.atan2(x, y) * 180) / Math.PI + 360) % 360,
      fromPole: MOON_RADIUS * colatitude,
    };
  }

  // Non-breaking spaces keep each value with its unit when a line wraps
  function position(lat, lon) {
    return `${Math.abs(lat).toFixed(3)}° S, ${lon.toFixed(2)}° E`;
  }

  /* ---------- Controls ---------- */

  function describePreset(preset) {
    const lowest = Math.min(...CRITERIA.map((criterion) => preset[criterion.key]));
    const raised = CRITERIA.filter((criterion) => preset[criterion.key] > lowest);
    return raised.length ? raised.map((criterion) => `${criterion.label} ×${preset[criterion.key] / lowest}`).join(", ") : "Equal weights";
  }

  function weightGlyph(preset) {
    const highest = Math.max(...CRITERIA.map((criterion) => preset[criterion.key]));
    const bars = CRITERIA.map((criterion) => `<i style="--c: var(--${criterion.key}); --h: ${Math.round((preset[criterion.key] / highest) * 100)}%"></i>`);
    return `<span class="weight-glyph" aria-hidden="true">${bars.join("")}</span>`;
  }

  function renderOptions(container, name, values, body) {
    container.innerHTML = values
      .map((value) => {
        const isDefault = value === DEFAULTS[name];
        return `<label class="option"${isDefault ? ' data-default title="The pipeline\'s default"' : ""}>
          <input type="radio" name="${name}" value="${value}"${value === state[name] ? " checked" : ""}>
          <span class="option-body">${body(value)}${isDefault ? '<span class="visually-hidden"> (default)</span>' : ""}</span>
        </label>`;
      })
      .join("");

    container.addEventListener("change", (event) => {
      const value = event.target.value;
      setState({ ...state, [name]: name === "weights" ? value : Number(value) });
    });
  }

  function syncOptions() {
    for (const name of ["pel", "distance", "weights"]) {
      const input = document.querySelector(`input[name="${name}"][value="${state[name]}"]`);
      if (input) input.checked = true;
    }
    $("reset").hidden = ["pel", "distance", "weights"].every((name) => state[name] === DEFAULTS[name]);
  }

  function setState(next) {
    state = next;
    syncOptions();
    writeHash();
    update({ refit: true });
  }

  $("reset").addEventListener("click", () => setState({ ...DEFAULTS }));

  renderOptions($("pel-options"), "pel", OPTIONS.pel, (value) => `${value}%`);
  renderOptions($("distance-options"), "distance", OPTIONS.distance, kilometres);
  renderOptions($("weight-options"), "weights", Object.keys(OPTIONS.weights), (key) => {
    const preset = OPTIONS.weights[key];
    return `<span class="option-title">${preset.label}</span><span class="option-detail">${describePreset(preset)}</span>${weightGlyph(preset)}`;
  });

  /* ---------- Site cards ---------- */

  // How a PSR ranks, by its best pair, at every threshold and distance under the current weights, as a
  // measure of how robust a site is. PELs are renumbered at each threshold, so the PSR is what's followed.
  function psrStanding(psr) {
    const standing = { settings: 0, first: 0, top: 0, lower: 0, out: 0, automatic: 0 };
    for (const pel of OPTIONS.pel) {
      for (const distance of OPTIONS.distance) {
        const config = DATA.configs[`${pel}|${distance}|${state.weights}`];
        const rank = config.ranks[psr];
        standing.settings++;
        if (rank === undefined) standing.out++;
        else if (rank > TOP_SITES) standing.lower++;
        else {
          standing.top++;
          if (rank === 1) standing.first++;
          // With this few pairs in range, every one of them makes the top 3
          if (config.pairs <= TOP_SITES) standing.automatic++;
        }
      }
    }
    return standing;
  }

  function stabilityNote(psr) {
    const standing = psrStanding(psr);
    const tally = [
      standing.first && `#1 in ${standing.first}`,
      `top ${TOP_SITES} in ${standing.top}`,
      standing.lower && `4th or lower in ${standing.lower}`,
      standing.out && `out of range in ${standing.out}`,
    ]
      .filter(Boolean)
      .map((item) => item.replaceAll(" ", " ")); // Each item wraps as a whole
    const automatic = standing.automatic
      ? `<p>In ${standing.automatic} of those ${standing.top}, ${TOP_SITES} or fewer pairs were in range, so a top ${TOP_SITES} place was automatic.</p>`
      : "";

    return `<div class="stability">
        <p>PSR ${psr} in all ${standing.settings} threshold and distance settings (${OPTIONS.weights[state.weights].label})</p>
        <p class="stability-tally">${tally.join(" · ")}</p>
        ${automatic}
      </div>`;
  }

  /* ---------- Reference sites ---------- */

  // The candidate landing site of Wueller et al. (2026) closest to a point, in projected metres
  function nearestReference([x, y]) {
    let nearest = null;
    for (const [name, region, siteX, siteY] of REFERENCE.sites) {
      const distance = Math.hypot(siteX - x, siteY - y);
      if (!nearest || distance < nearest.distance) nearest = { name, region: REFERENCE.regions[region], distance };
    }
    return nearest;
  }

  function referenceStatus(region) {
    return region.artemisIII ? "Artemis III region" : "Not an Artemis III region";
  }

  // Measured from the PEL, where a lander would set down
  function referenceNote(site) {
    if (!REFERENCE) return "";
    const nearest = nearestReference(site.pel_point);
    const km = nearest.distance / 1000;
    return `<p class="reference-note">
        Nearest Wueller et al. site: <strong>${nearest.name}</strong>, ${nearest.region.name},
        ${km < 10 ? km.toFixed(1) : Math.round(km)} km from the PEL
        <span class="tag${nearest.region.artemisIII ? " is-artemis" : ""}">${referenceStatus(nearest.region)}</span>
      </p>`;
  }

  function siteCard(site, rank) {
    const { fromPole } = toLatLon(...site.mid);
    const share = (part) => (site.total > 0 ? Math.round((part / site.total) * 100) : 0);
    const segments = CRITERIA.filter((criterion) => site.parts[criterion.key] > 0.0005).map(
      (criterion) => `<span class="seg" data-criterion="${criterion.key}" style="--c: var(--${criterion.key}); --part: ${site.parts[criterion.key]}"></span>`
    );
    const barLabel = `Score ${site.total.toFixed(3)}: ` + CRITERIA.map((criterion) => `${criterion.label.toLowerCase()} ${site.parts[criterion.key].toFixed(3)}`).join(", ");

    const card = document.createElement("li");
    card.className = "site";
    card.tabIndex = 0;
    card.dataset.rank = rank;
    card.title = "Show on the map";
    card.innerHTML = `
      <div class="site-top">
        <span class="rank" aria-hidden="true">${rank}</span>
        <div>
          <h3>PSR ${site.psr} <span class="arrow">→</span> PEL ${site.pel}</h3>
          <p class="coords">${position(site.lat, site.lon)} · ${(fromPole / 1000).toFixed(1)} km from the pole</p>
        </div>
        <div class="score">
          <span class="score-value">${site.total.toFixed(3)}</span>
          <span class="score-label">score</span>
        </div>
      </div>
      <div class="bar" role="img" aria-label="${barLabel}">
        <div class="bar-fill" style="width: ${(site.total * 100).toFixed(2)}%">${segments.join("")}</div>
      </div>
      <dl class="metrics">
        <div>
          <dt><span class="swatch" style="--c: var(--distance)"></span>Walk</dt>
          <dd>${integer.format(Math.round(site.distance_m))} m<span class="part">+${site.parts.distance.toFixed(3)} (${share(site.parts.distance)}%)</span></dd>
        </div>
        <div>
          <dt><span class="swatch" style="--c: var(--illumination)"></span>PEL sunlit</dt>
          <dd>${site.pel_illumination.toFixed(1)}%<span class="part">+${site.parts.illumination.toFixed(3)} (${share(site.parts.illumination)}%)</span></dd>
        </div>
        <div>
          <dt><span class="swatch" style="--c: var(--size)"></span>PSR area</dt>
          <dd>${area(site.psr_area_km2)}<span class="part">+${site.parts.size.toFixed(3)} (${share(site.parts.size)}%)</span></dd>
        </div>
      </dl>
      ${referenceNote(site)}
      ${stabilityNote(site.psr)}`;

    card.addEventListener("click", () => selectSite(rank));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectSite(rank);
      }
    });
    card.addEventListener("mouseenter", () => setActive(rank));
    card.addEventListener("mouseleave", () => setActive(null));

    for (const segment of card.querySelectorAll(".seg")) {
      const criterion = CRITERIA.find((item) => item.key === segment.dataset.criterion);
      const part = site.parts[criterion.key];
      segment.addEventListener("pointerenter", (event) =>
        showTooltip(event, `<strong><span class="swatch" style="--c: var(--${criterion.key})"></span>${criterion.label}</strong>
          <span>${part.toFixed(3)} of the ${site.total.toFixed(3)} total (${share(part)}%)</span>`)
      );
      segment.addEventListener("pointermove", moveTooltip);
      segment.addEventListener("pointerleave", hideTooltip);
    }

    return card;
  }

  function renderSites(config) {
    const list = $("site-list");
    list.replaceChildren(...config.sites.map((site, index) => siteCard(site, index + 1)));

    if (config.sites.length < 3) {
      const empty = document.createElement("li");
      empty.className = "site-empty";
      empty.textContent =
        (config.sites.length === 0 ? "No pairs qualify" : `Only ${config.sites.length === 1 ? "one pair qualifies" : "two pairs qualify"}`) +
        " under this configuration. Lower the PEL threshold or allow a longer walk to see more.";
      list.append(empty);
    }

    const pairs = config.pairs === 1 ? "pair" : "pairs";
    $("summary").innerHTML =
      `<strong>${integer.format(config.pairs)}</strong> PSR–PEL ${pairs} within ${kilometres(state.distance)}, ` +
      `drawn from ${integer.format(DATA.counts.psr)} PSRs and ${integer.format(DATA.counts.pel[state.pel])} PELs ` +
      `that pass the size and slope filters.`;
  }

  /* ---------- Tooltip ---------- */

  const tooltip = $("tooltip");

  function showTooltip(event, html) {
    tooltip.innerHTML = html;
    tooltip.hidden = false;
    moveTooltip(event);
  }

  function moveTooltip(event) {
    const { width, height } = tooltip.getBoundingClientRect();
    const left = Math.min(event.clientX + 14, window.innerWidth - width - 8);
    const top = event.clientY - height - 12 < 8 ? event.clientY + 18 : event.clientY - height - 12;
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
  }

  function hideTooltip() {
    tooltip.hidden = true;
  }

  /* ---------- Map ---------- */

  // Tile pixels at zoom z map to projected metres as in the tile pyramid, where one tile pixel at
  // RASTER.tileZoom is one raster pixel; the scale bar reads in metres for the same reason
  const scale = 1 / (RASTER.pixelSize * 2 ** RASTER.tileZoom);
  const crs = L.extend({}, L.CRS.Simple, {
    transformation: new L.Transformation(scale, -RASTER.west * scale, -scale, RASTER.north * scale),
  });
  const rasterBounds = L.latLngBounds(
    [RASTER.north - RASTER.height * RASTER.pixelSize, RASTER.west],
    [RASTER.north, RASTER.west + RASTER.width * RASTER.pixelSize]
  );

  const map = L.map("map", {
    crs,
    zoomSnap: 0.25,
    zoomDelta: 0.5,
    wheelPxPerZoomLevel: 90,
    minZoom: 1,
    maxZoom: RASTER.tileZoom + 2,
    maxBounds: rasterBounds.pad(0.15),
    maxBoundsViscosity: 0.8,
    zoomAnimation: !reduceMotion,
  });
  map.fitBounds(rasterBounds);
  map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');

  L.tileLayer("tiles/{z}/{x}/{y}.webp", {
    tileSize: RASTER.tileSize,
    minNativeZoom: 0,
    maxNativeZoom: RASTER.tileZoom,
    bounds: rasterBounds,
    noWrap: true,
    attribution: '<a href="https://pgda.gsfc.nasa.gov/products/69">NASA LOLA</a>',
  }).addTo(map);

  // Panes keep the layers in order: graticule, then regions, then the walks, then the pins
  map.createPane("graticule").style.zIndex = 350;
  map.createPane("regions").style.zIndex = 380;

  function label(latlng, html, className = "grid-label") {
    return L.marker(latlng, {
      icon: L.divIcon({ className, html, iconSize: null }),
      interactive: false,
      keyboard: false,
    });
  }

  function drawGraticule() {
    const lines = { pane: "graticule", color: "#f0efec", opacity: 0.2, weight: 1, dashArray: "2 5", interactive: false };
    const inner = DATA.rings[0].radius;
    const outer = DATA.rings[DATA.rings.length - 1].radius;

    for (const ring of DATA.rings) {
      L.circle([0, 0], { ...lines, radius: ring.radius, fill: false }).addTo(map);
      label([ring.radius, 0], `<span>${ring.lat}° S</span>`).addTo(map);
    }

    // Meridians start at the innermost ring, to keep the crowded ground around the pole clear.
    // Longitude runs clockwise from 0° at the top of the map, as x = r sin(lon) and y = r cos(lon).
    for (let lon = 0; lon < 360; lon += 30) {
      const angle = (lon * Math.PI) / 180;
      const point = (radius) => [radius * Math.cos(angle), radius * Math.sin(angle)];
      L.polyline([point(inner), point(outer)], lines).addTo(map);
      label(point(outer * 0.94), `<span>${lon === 0 || lon === 180 ? `${lon}°` : `${lon}° E`}</span>`).addTo(map);
    }

    label([0, 0], '<span class="pole-cross"></span><span class="pole-text">90° S</span>', "pole-label").addTo(map);
  }

  drawGraticule();
  L.control.scale({ imperial: false, position: "bottomright", maxWidth: 140 }).addTo(map);

  // Legend, with the readout of the cursor's position underneath
  const Panel = L.Control.extend({
    onAdd() {
      const element = L.DomUtil.create("div", `map-panel ${this.options.className}`);
      element.innerHTML = this.options.html;
      L.DomEvent.disableClickPropagation(element);
      return element;
    },
  });

  const referenceLegend = REFERENCE
    ? `<div class="legend-reference">
        <label class="legend-toggle"><input type="checkbox" id="reference-toggle" checked>Wueller et al. (2026) sites</label>
        <ul>
          <li><span class="ref-dot is-artemis"></span>In an Artemis III region</li>
          <li><span class="ref-dot"></span>In another region</li>
        </ul>
      </div>`
    : "";

  new Panel({
    position: "topright",
    className: "map-legend",
    html: `<ul>
      <li><span class="swatch" style="--c: var(--size)"></span>PSR: shadowed, holds ice</li>
      <li><span class="swatch" style="--c: var(--illumination)"></span>PEL: sunlit ridge</li>
      <li><span class="legend-walk"></span>Shortest walk between them</li>
      <li><span class="legend-pin">1</span>Site rank</li>
    </ul>${referenceLegend}`,
  }).addTo(map);

  // Wueller et al. (2026)'s candidate landing sites, kept under the site pins
  const referenceLayer = L.layerGroup();
  if (REFERENCE) {
    for (const [name, code, x, y] of REFERENCE.sites) {
      const region = REFERENCE.regions[code];
      L.marker(toLatLng([x, y]), {
        icon: L.divIcon({ className: "ref-anchor", html: `<span class="ref-dot${region.artemisIII ? " is-artemis" : ""}"></span>`, iconSize: [12, 12] }),
        keyboard: false,
        zIndexOffset: -1000,
      })
        .bindTooltip(`<strong>${name}</strong><span>${region.name}</span><span>${referenceStatus(region)}</span>`, {
          className: "ref-tooltip",
          direction: "top",
          offset: [0, -6],
        })
        .addTo(referenceLayer);
    }
    referenceLayer.addTo(map);
    $("reference-toggle").addEventListener("change", (event) => {
      event.target.checked ? referenceLayer.addTo(map) : referenceLayer.remove();
    });
  }

  const readout = new Panel({ position: "bottomleft", className: "readout", html: "" }).addTo(map);

  map.on("mousemove", (event) => {
    const { lat, lng } = event.latlng;
    if (!rasterBounds.contains(event.latlng)) return readout.getContainer().replaceChildren();
    const point = toLatLon(lng, lat);
    readout.getContainer().textContent = position(point.lat, point.lon);
  });
  map.on("mouseout", () => readout.getContainer().replaceChildren());

  // Buttons to frame the current sites or the whole map
  const Views = L.Control.extend({
    onAdd() {
      const bar = L.DomUtil.create("div", "leaflet-bar");
      bar.innerHTML = `
        <button type="button" data-view="sites" title="Frame the top sites" aria-label="Frame the top sites">◎</button>
        <button type="button" data-view="all" title="Show the whole map" aria-label="Show the whole map">⤢</button>`;
      L.DomEvent.disableClickPropagation(bar);
      L.DomEvent.on(bar, "click", (event) => {
        const view = event.target.closest("button")?.dataset.view;
        if (view === "sites") fitSites(true);
        if (view === "all") map.flyToBounds(rasterBounds, { duration: 0.8, animate: !reduceMotion });
      });
      return bar;
    },
  });
  new Views({ position: "topleft" }).addTo(map);

  const sitesLayer = L.layerGroup().addTo(map);

  function renderMap(config) {
    sitesLayer.clearLayers();
    const drawn = new Set(); // Neighbouring sites can share a region; draw each once

    siteLayers = config.sites.map((site, index) => {
      const rank = index + 1;
      const bounds = L.latLngBounds([toLatLng(site.psr_point), toLatLng(site.pel_point)]);

      for (const key of site.overlays) {
        const overlay = DATA.overlays[key];
        bounds.extend(overlay.bounds);
        if (drawn.has(key)) continue;
        drawn.add(key);
        L.imageOverlay(overlay.png, overlay.bounds, { pane: "regions", className: "region", interactive: false }).addTo(sitesLayer);
      }

      const walk = [toLatLng(site.psr_point), toLatLng(site.pel_point)];
      L.polyline(walk, { color: "#000", opacity: 0.6, weight: 5, interactive: false }).addTo(sitesLayer);
      L.polyline(walk, { color: css("--distance"), weight: 2, dashArray: "5 4", interactive: false }).addTo(sitesLayer);

      const pin = L.marker(toLatLng(site.mid), {
        icon: L.divIcon({ className: "pin-anchor", html: `<span class="pin">${rank}</span>`, iconSize: [28, 34], iconAnchor: [14, 34] }),
        title: `Site ${rank}: ${site.pair}`,
        alt: `Site ${rank}`,
        zIndexOffset: 1000 - rank,
        riseOnHover: true,
      }).addTo(sitesLayer);

      pin.on("click", () => {
        selectSite(rank);
        const card = document.querySelector(`.site[data-rank="${rank}"]`);
        // Only when the cards have their own column; otherwise scrolling would take the map off screen
        if (window.matchMedia("(min-width: 1200px)").matches) card?.scrollIntoView({ block: "nearest", behavior: reduceMotion ? "auto" : "smooth" });
      });
      pin.on("mouseover", () => setActive(rank));
      pin.on("mouseout", () => setActive(null));

      return { rank, bounds, pin };
    });

    spreadPins();
  }

  // Pins that would overlap at the current zoom are set side by side around their shared centre
  function spreadPins() {
    const groups = [];
    for (const layer of siteLayers) {
      const point = map.latLngToLayerPoint(layer.pin.getLatLng());
      const group = groups.find((members) => members.some((member) => member.point.distanceTo(point) < PIN_SPACING));
      group ? group.push({ layer, point }) : groups.push([{ layer, point }]);
    }

    for (const group of groups) {
      group.forEach(({ layer }, index) => {
        const offset = (index - (group.length - 1) / 2) * PIN_SPACING;
        layer.pin.getElement()?.querySelector(".pin").style.setProperty("--offset", `${offset}px`);
      });
    }
  }

  map.on("zoomend", spreadPins);

  function fitSites(animate) {
    if (!siteLayers.length) return map.fitBounds(rasterBounds);
    const bounds = L.latLngBounds([]);
    for (const layer of siteLayers) bounds.extend(layer.bounds);
    map.flyToBounds(bounds, { padding: [80, 80], maxZoom: RASTER.tileZoom + 1, duration: 0.9, animate: animate && !reduceMotion });
  }

  /* ---------- Linking the cards and the map ---------- */

  function setActive(rank) {
    for (const card of document.querySelectorAll(".site")) card.classList.toggle("is-active", Number(card.dataset.rank) === rank);
    for (const layer of siteLayers) layer.pin.getElement()?.classList.toggle("is-active", layer.rank === rank);
  }

  function selectSite(rank) {
    const layer = siteLayers[rank - 1];
    if (!layer) return;
    for (const card of document.querySelectorAll(".site")) card.classList.toggle("is-selected", Number(card.dataset.rank) === rank);
    map.flyToBounds(layer.bounds, { padding: [90, 90], maxZoom: RASTER.tileZoom + 2, duration: 0.9, animate: !reduceMotion });
  }

  /* ---------- Rendering ---------- */

  function update({ refit }) {
    const config = DATA.configs[`${state.pel}|${state.distance}|${state.weights}`];
    hideTooltip();
    renderSites(config);
    renderMap(config);
    if (refit) fitSites(true);
  }

  window.addEventListener("hashchange", () => {
    state = readHash();
    syncOptions();
    update({ refit: true });
  });

  $("generated").textContent = `Results generated ${DATA.generated}`;
  syncOptions();
  update({ refit: false });
  fitSites(false);
})();
