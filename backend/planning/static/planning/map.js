// Planning Mapper - front end
// Step 1: set up the Leaflet map.

// TODO 1: create a Leaflet map in the element with id "map",
//         centred on Westport (lat 53.80, lng -9.52), zoom level 11.
// Leaflet wants [lat, lng] here. (The API/GeoJSON use [lng, lat] - watch out in step 2.)
const map = L.map("map").setView([53.80, -9.52], 11);

// TODO 2: add the OpenStreetMap tile layer.
// The attribution is required by the OSM licence, so don't remove it.
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution:
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

// Step 2: load the planning applications from the API and show them on the map.
// The API (GeoFeatureModelSerializer) hands back a GeoJSON FeatureCollection,
// so L.geoJSON can read it directly - no manual lat/lng swapping needed here.

// A different colour per status, so the map is readable at a glance.
const STATUS_COLOURS = {
  PENDING:"#f0ad4e",
  GRANTED:"#5cb85c",
  REFUSED:"#d9534f",
  WITHDRAWN:"#777777",
};

function styleByStatus(feature) {
  const colour = STATUS_COLOURS[feature.properties.status] || "#337ab7";
  return {
    radius: 6,
    color: colour,
    fillColor: colour,
    fillOpacity: 0.8,
    weight: 1,
  };
}

function popupHtml(feature) {
  const p = feature.properties;
  return `
    <strong>${p.reference}</strong><br>
    ${p.description}<br>
    <em>${p.address || "No address given"}</em><br>
    Status: ${p.status}<br>
    Received: ${p.received_date}
  `;
}

fetch("/api/applications/")
  .then((response) => {
    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`);
    }
    return response.json();
  })
  .then((geojson) => {
    L.geoJSON(geojson, {
      // Points need pointToLayer, otherwise Leaflet draws plain default markers.
      pointToLayer: (feature, latlng) => L.circleMarker(latlng, styleByStatus(feature)),
      onEachFeature: (feature, layer) => layer.bindPopup(popupHtml(feature)),
    }).addTo(map);
  })
  .catch((error) => {
    console.error("Could not load planning applications:", error);
  });

function popupHtmlWithDistance(feature) {
  const base = popupHtml(feature);
  const distance = feature.properties.distance_m;
  return distance != null ? `${base}Distance: ${Math.round(distance)} m<br>` : base;
}

// Step 3: the "Spatial queries" sidebar.
// Each form just arms a query; the actual lat/lng comes from the next map click,
// since none of the query endpoints need anything the user can't just click on.

const statusEl = document.getElementById("query-status");
const resultsLayer = L.layerGroup().addTo(map); // holds the clicked point + the result markers

let pendingQuery = null; // set by a form submit, consumed by the next map click

function armQuery(run, message) {
  pendingQuery = run;
  statusEl.textContent = message;
}

function showError(error) {
  console.error(error);
  statusEl.textContent = "Something went wrong - see the console for details.";
}

// Marks the point that was clicked, then clears old results so they don't pile up.
function markClickedPoint(latlng) {
  resultsLayer.clearLayers();
  L.circleMarker(latlng, { radius: 5, color: "#000", weight: 2, fillOpacity: 0 }).addTo(resultsLayer);
}

function showApplicationResults(geojson, label) {
  L.geoJSON(geojson, {
    pointToLayer: (_feature, latlng) =>
      L.circleMarker(latlng, { radius: 8, color: "#000", fillColor: "#ffd43b", fillOpacity: 0.9, weight: 2 }),
    onEachFeature: (feature, layer) => layer.bindPopup(popupHtmlWithDistance(feature)),
  }).addTo(resultsLayer);
  statusEl.textContent = `${label}: ${geojson.features.length} found.`;
}

document.getElementById("nearest-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const n = document.getElementById("nearest-n").value;
  armQuery((latlng) => {
    fetch(`/api/applications/nearest/?lat=${latlng.lat}&lng=${latlng.lng}&n=${n}`)
      .then((response) => response.json())
      .then((geojson) => showApplicationResults(geojson, `Nearest ${n} applications`))
      .catch(showError);
  }, "Click the map to find the nearest applications...");
});

document.getElementById("within-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const km = document.getElementById("within-km").value;
  armQuery((latlng) => {
    fetch(`/api/applications/within/?lat=${latlng.lat}&lng=${latlng.lng}&km=${km}`)
      .then((response) => response.json())
      .then((geojson) => showApplicationResults(geojson, `Applications within ${km} km`))
      .catch(showError);
  }, "Click the map to search within a radius...");
});

document.getElementById("locate-form").addEventListener("submit", (event) => {
  event.preventDefault();
  armQuery((latlng) => {
    fetch(`/api/counties/locate/?lat=${latlng.lat}&lng=${latlng.lng}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error("That point isn't inside any loaded county.");
        }
        return response.json();
      })
      .then((county) => {
        statusEl.textContent = `That point is in ${county.name}.`;
      })
      .catch(showError);
  }, "Click the map to find its county...");
});

document.getElementById("clear-results").addEventListener("click", () => {
  resultsLayer.clearLayers();
  pendingQuery = null;
  statusEl.textContent = "";
});

// The one map click handler that every form above shares.
map.on("click", (event) => {
  if (!pendingQuery) {
    return; // no tool armed - an ordinary click on the map, ignore it
  }
  markClickedPoint(event.latlng);
  pendingQuery(event.latlng);
  pendingQuery = null;
});
