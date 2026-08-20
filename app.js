document.addEventListener("DOMContentLoaded", () => {
    loadStatuteIndex();
});

async function loadStatuteIndex() {
    const selector = document.getElementById("statute-select");
    
    try {
        const response = await fetch("./data/index.json");
        if (!response.ok) throw new Error("Could not load statute index.");
        
        const manifest = await response.json();
        selector.innerHTML = ""; // Clear loading message

        manifest.forEach(item => {
            const option = document.createElement("option");
            option.value = item.id;
            option.textContent = `MCA ${item.id}: ${item.title}`;
            selector.appendChild(option);
        });

        // Event listener to change statute when selection changes
        selector.addEventListener("change", (e) => {
            if (e.target.value) {
                fetchStatute(e.target.value);
            }
        });

        // Load the first statute in the manifest by default
        if (manifest.length > 0) {
            fetchStatute(manifest[0].id);
        }

    } catch (error) {
        selector.innerHTML = `<option>Error loading index</option>`;
        document.getElementById("loading").innerText = `Error loading statute index: ${error.message}`;
    }
}

async function fetchStatute(statuteId) {
    document.getElementById("loading").classList.remove("hidden");
    document.getElementById("loading").innerText = "Loading statute data...";

    try {
        const response = await fetch(`./data/${statuteId}.json`);
        if (!response.ok) throw new Error(`Statute ${statuteId} not found.`);
        
        const data = await response.json();
        renderStatute(data);
    } catch (error) {
        document.getElementById("loading").innerText = `Error: ${error.message}`;
    }
}

function renderStatute(data) {
    document.getElementById("loading").classList.add("hidden");
    
    document.getElementById("statute-id").innerText = `MCA ${data.law_id}`;
    document.getElementById("statute-title").innerText = data.title_full;
    document.getElementById("statute-history").innerText = data.history || "N/A";

    const container = document.getElementById("statute-subsections");
    container.innerHTML = ""; 

    data.subsections.forEach(item => {
        // Skip parent containers that have no direct body text
        if (!item.text) return;

        const p = document.createElement("p");
        p.id = item.path; // Enables direct URL linking like #45-5-206#(4)(b)(iii)
        p.className = `subsection-item indent-${item.indent}`;

        // Get the last marker segment from path for visual display (e.g., "(4)(b)(iii)" -> "(iii)")
        const pathSegments = item.path.match(/\((?:[0-9]+|[a-z]+|[A-Z]+)\)/g) || [];
        const label = pathSegments[pathSegments.length - 1] || "";

        p.innerText = `${label} ${item.text}`;
        container.appendChild(p);
    });
}
