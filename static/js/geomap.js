// Initialize the map
const map = L.map('map').setView([25.2, 55.3], 5);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// Create a marker-cluster group
const markers = L.markerClusterGroup();
map.addLayer(markers);

// Cache UI elements
const autoRefresh = document.getElementById('auto-refresh');
const refreshBtn  = document.getElementById('refresh-btn');
const countSpan   = document.getElementById('count-value');
const lastFetched = document.getElementById('last-fetched');

// Function to load data and update the map
async function loadData() {
  try {
    const res   = await fetch('/api/geomap_data');
    const flows = await res.json();

    // Clear old markers
    markers.clearLayers();

    // Add new markers
    flows.forEach(f => {
      if (f.lat && f.lon) {
        const m = L.circleMarker([f.lat, f.lon], { radius: 6 });
        m.bindPopup(
          `<strong>${f.ip}</strong><br>` +
          `${new Date(f.time).toLocaleString()}`
        );
        markers.addLayer(m);
      }
    });

    // Update counts and timestamp
    countSpan.textContent   = flows.length;
    lastFetched.textContent = new Date().toLocaleString();
  } catch (err) {
    console.error('Error loading data:', err);
  }
}

// Initial load
loadData();

// Manual refresh
refreshBtn.addEventListener('click', loadData);

// Auto-refresh every 60s if checkbox is checked
setInterval(() => {
  if (autoRefresh.checked) loadData();
}, 60000);
