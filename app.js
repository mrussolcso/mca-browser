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
    
    document.getElementById("statute-id").innerText = `MCA ${data.id}`;
    document.getElementById("statute-title").innerText = data.title;
    document.getElementById("statute-history").innerText = data.history || "N/A";
    
    const sourceLink = document.getElementById("source-link");
    if (sourceLink) {
        sourceLink.href = data.source_url;
    }

    // Render formatted subsections
    const container = document.getElementById("statute-subsections");
    container.innerHTML = ""; 

    data.subsections.forEach(line => {
        const p = document.createElement("p");
        p.className = "subsection-item";
        
        const trimmed = line.trim();

        // Level 2 indent: (a), (b), (c)
        if (/^\([a-z]\)/.test(trimmed)) {
            p.classList.add("indent-1");
        } 
        // Level 3 indent: (i), (ii), (iii)
        else if (/^\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\)/.test(trimmed)) {
            p.classList.add("indent-2");
        }

        p.innerText = trimmed;
        container.appendChild(p);
    });
}
