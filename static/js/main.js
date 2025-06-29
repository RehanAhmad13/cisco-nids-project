// ===============================
// Plot Mode Switcher
// ===============================
document.getElementById('btn-general')  .addEventListener('click', loadGeneral);
document.getElementById('btn-direction').addEventListener('click', loadByDirection);
document.getElementById('btn-interface').addEventListener('click', loadByInterface);

// On page load, show General
loadGeneral();

// ─────────────────────────────────────────────────────────────────────────────
//  Helper: build checkbox toggles for each trace
// ─────────────────────────────────────────────────────────────────────────────
function generateToggles(names) {
  const container = document.getElementById('trace-toggles');
  container.innerHTML = '';  // clear any old
  names.forEach((name, idx) => {
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.id = `toggle-${idx}`;
    cb.checked = true;
    cb.dataset.traceIndex = idx;
    cb.addEventListener('change', e => {
      const vis = e.target.checked ? true : 'legendonly';
      Plotly.restyle('bytesChart', { visible: vis }, [e.target.dataset.traceIndex]);
    });

    const label = document.createElement('label');
    label.htmlFor = cb.id;
    label.textContent = name;

    container.appendChild(cb);
    container.appendChild(label);
    container.appendChild(document.createTextNode(' \u00A0')); // spacer
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// 1) General mode: fetch /data, update bytesChart, throughputChart & table
//    also clear any toggles
// ─────────────────────────────────────────────────────────────────────────────
async function loadGeneral() {
  // clear toggles row
  document.getElementById('trace-toggles').innerHTML = '';

  try {
    const res  = await fetch('/data');
    const data = await res.json();

    const times      = data.map(d => new Date(d.time_first));
    const bytes      = data.map(d => d.in_bytes ?? 0);
    const throughput = data.map(d => d.avg_throughput_bps ?? 0);

    // Bytes/sec plot
    Plotly.newPlot('bytesChart', [{
      x: times,
      y: bytes,
      mode: 'lines+markers',
      name: 'In Bytes',
    }], layout());

    // Throughput plot
    Plotly.newPlot('throughputChart', [{
      x: times,
      y: throughput,
      mode: 'lines+markers',
      name: 'Throughput (bps)',
    }], layout());

    // Fill Latest Flows table
    const tbody = document.getElementById("flowTableBody");
    tbody.innerHTML = "";
    data.slice(0, 10).forEach(d => {
      const displayTime = new Date(d.time_first).toLocaleString('en-GB', {
        day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false
      });
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${displayTime}</td>
        <td>${d.ipv4_src_addr ?? '—'}</td>
        <td>${d.ipv4_dst_addr ?? '—'}</td>
        <td>${d.l4_src_port ?? '—'}</td>
        <td>${d.l4_dst_port ?? '—'}</td>
        <td>${d.protocol ?? '—'}</td>
        <td>${d.tcp_flags ?? '—'}</td>
        <td>${d.in_bytes ?? '—'}</td>
        <td>${d.in_pkts ?? '—'}</td>
        <td>${d.flow_duration_ms ?? '—'}</td>
      `;
      tbody.appendChild(row);
    });

  } catch (err) {
    console.error("Error loading general data:", err);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 2) By Direction mode: fetch /bytes_by_direction, update bytesChart + toggles
// ─────────────────────────────────────────────────────────────────────────────
async function loadByDirection() {
  try {
    const res  = await fetch('/bytes_by_direction');
    const data = await res.json();

    const dirs = Array.from(new Set(data.map(d => d.direction)));
    const traces = dirs.map(dir => {
      const pts = data.filter(d => d.direction === dir);
      return {
        x: pts.map(d => new Date(d.ts)),
        y: pts.map(d => d.bytes),
        mode: 'lines+markers',
        name: dir,
      };
    });

    Plotly.newPlot('bytesChart', traces, layout());
    // build checkboxes
    generateToggles(dirs);

  } catch (err) {
    console.error("Error loading by-direction data:", err);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 3) By Interface mode: fetch /bytes_by_interface, update bytesChart + toggles
// ─────────────────────────────────────────────────────────────────────────────
async function loadByInterface() {
  try {
    const res  = await fetch('/bytes_by_interface');
    const data = await res.json();

    const ifs = Array.from(new Set(data.map(d => d.ingress_if)));
    const traces = ifs.map(i => {
      const pts = data.filter(d => d.ingress_if === i);
      return {
        x: pts.map(d => new Date(d.ts)),
        y: pts.map(d => d.bytes),
        mode: 'lines+markers',
        name: `IF ${i}`,
      };
    });

    Plotly.newPlot('bytesChart', traces, layout());
    // build checkboxes
    generateToggles(ifs.map(i => `IF ${i}`));

  } catch (err) {
    console.error("Error loading by-interface data:", err);
  }
}

// ===============================
// Fetch and update network metrics from '/metrics' (unchanged)
// ===============================
async function fetchMetrics() {
  try {
    const res    = await fetch('/metrics');
    const json   = await res.json();
    const times  = json.timeseries.map(d => new Date(d.minute));
    const bytes  = json.timeseries.map(d => d.total_bytes ?? 0);
    const packets = json.timeseries.map(d => d.total_packets ?? 0);
    const flowCounts = json.timeseries.map(d => d.flow_count ?? 0);
    const talkers = json.top_talkers;

    Plotly.newPlot('packetsChart', [{
      x: times,
      y: packets,
      mode: 'lines+markers',
      name: 'In Packets',
    }], layout());

    Plotly.newPlot('flowCountChart', [{
      x: times,
      y: flowCounts,
      mode: 'lines+markers',
      name: 'Flow Count',
    }], layout());

    Plotly.newPlot('topTalkersChart', [{
      x: talkers.map(d => d.ipv4_src_addr),
      y: talkers.map(d => d.total_bytes),
      type: 'bar',
      name: 'Top Talkers',
    }], {
      margin: { t: 30 },
      plot_bgcolor: 'white',
      paper_bgcolor: 'white',
      font: { color: '#1c1c1c' }
    });

  } catch (err) {
    console.error("Error fetching /metrics:", err);
  }
}

// ===============================
// Layout configuration shared across all plots (unchanged)
// ===============================
function layout() {
  return {
    xaxis: {
      tickformat: "%H:%M",
      tickangle: -45,
      title: "Time (HH:MM)",
      type: "date"
    },
    margin: { t: 30 },
    plot_bgcolor: "#ffffff",
    paper_bgcolor: "#ffffff",
    font: { color: "#1c1c1c" }
  };
}

// ===============================
// Main execution & auto-refresh
// ===============================
fetchMetrics();
setInterval(() => {
  loadGeneral();   // reload general bytes + table
  fetchMetrics();  // reload metrics charts
}, 60000);
