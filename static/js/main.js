// ===============================
// Fetch and update flow-by-flow data from '/data'
// ===============================
async function fetchDataAndUpdateUI() {
  try {
    // Fetch the flow-level data from backend /data route
    const res = await fetch('/data');
    const data = await res.json(); // Parse the JSON response

    // Extract time, incoming bytes, and throughput from the data
    const times = data.map(d => new Date(d.time_first)); // Convert 'time_first' into JS Date objects
    const bytes = data.map(d => d.in_bytes ?? 0); // Incoming bytes (use 0 if missing)
    const throughput = data.map(d => d.avg_throughput_bps ?? 0); // Throughput in bits per second (0 if missing)

    // Plot the Incoming Bytes over Time chart
    Plotly.newPlot('bytesChart', [{
      x: times,               // X-axis: time of flows
      y: bytes,               // Y-axis: in_bytes values
      mode: 'lines+markers',   // Show both lines and points
      name: 'In Bytes',        // Legend label
      line: { color: '#2196F3' } // Line color: blue
    }], layout());            // Use shared layout configuration

    // Plot the Throughput (bps) over Time chart
    Plotly.newPlot('throughputChart', [{
      x: times, 
      y: throughput,
      mode: 'lines+markers',
      name: 'Throughput (bps)',
      line: { color: '#4CAF50' } // Line color: green
    }], layout());

    // ========================
    // Populate the flow data table
    // ========================

    const tbody = document.getElementById("flowTableBody"); // Get the table body element
    tbody.innerHTML = ""; // Clear any old rows before filling new data

    // For the first 10 flows, create table rows
    data.slice(0, 10).forEach(d => {
      const row = document.createElement("tr");

      // Format timestamp nicely for display
      const displayTime = new Date(d.time_first).toLocaleString('en-GB', {
        day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false
      });

      // Fill in the columns with flow details (show '—' if value is missing)
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
      
      tbody.appendChild(row); // Add the row to the table
    });

  } catch (err) {
    console.error("Error fetching /data:", err); // Log error if API call fails
  }
}

// ===============================
// Fetch and update network metrics from '/metrics'
// ===============================
async function fetchMetrics() {
  try {
    // Fetch the summarized metrics data from backend /metrics route
    const res = await fetch('/metrics');
    const json = await res.json(); // Parse JSON

    const metrics = json.timeseries;   // Time-based metrics (total bytes, packets, etc.)
    const talkers = json.top_talkers;  // Top talker IPs by bytes

    // Extract individual metric arrays for plotting
    const times = metrics.map(d => new Date(d.minute));         // Per-minute timestamps
    const bytes = metrics.map(d => d.total_bytes ?? 0);          // Total bytes per minute
    const packets = metrics.map(d => d.total_packets ?? 0);      // Total packets per minute
    const flowCounts = metrics.map(d => d.flow_count ?? 0);      // Number of flows per minute
    const avgThroughput = metrics.map(d => d.avg_throughput ?? 0); // Avg throughput per minute

    // Plot In Packets over Time chart
    Plotly.newPlot('packetsChart', [{
      x: times,
      y: packets,
      mode: 'lines+markers',
      name: 'In Packets',
      line: { color: '#FF9800' } // Line color: orange
    }], layout());

    // Plot Flow Count per Minute chart
    Plotly.newPlot('flowCountChart', [{
      x: times,
      y: flowCounts,
      mode: 'lines+markers',
      name: 'Flow Count',
      line: { color: '#9C27B0' } // Line color: purple
    }], layout());

    // Plot Top Talkers (bar chart of top IPs by bytes)
    Plotly.newPlot('topTalkersChart', [{
      x: talkers.map(d => d.ipv4_src_addr), // IP addresses as x-axis
      y: talkers.map(d => d.total_bytes),   // Total bytes per IP as y-axis
      type: 'bar',                          // Bar chart
      marker: { color: '#03A9F4' },          // Bar color: light blue
      name: 'Top Talkers (bytes)'
    }], {
      margin: { t: 30 },                    // Reduce top margin
      plot_bgcolor: 'white',                 // White plot background
      paper_bgcolor: 'white',                // White outer background
      font: { color: '#1c1c1c' }             // Dark gray font
    });

  } catch (err) {
    console.error("Error fetching /metrics:", err); // Log any fetch error
  }
}

// ===============================
// Layout configuration shared across all plots
// ===============================
function layout() {
  return {
    xaxis: {
      tickformat: "%H:%M",  // Show only hours and minutes
      tickangle: -45,       // Rotate tick labels for readability
      title: "Time (HH:MM)",// X-axis title
      type: "date"          // Treat X-axis as datetime
    },
    margin: { t: 30 },      // Top margin (space for title, etc.)
    plot_bgcolor: "#ffffff",// Plot background color
    paper_bgcolor: "#ffffff",// Overall canvas background
    font: { color: "#1c1c1c" } // Font color
  };
}

// ===============================
// Main execution
// ===============================

// First fetch and render data when page loads
fetchDataAndUpdateUI();
fetchMetrics();

// Refresh the dashboard every 60 seconds (1 minute)
setInterval(() => {
  fetchDataAndUpdateUI();  // Re-fetch raw flow data and update table + charts
  fetchMetrics();          // Re-fetch summarized metrics and update charts
}, 60000);
