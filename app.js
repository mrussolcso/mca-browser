document.addEventListener("DOMContentLoaded", () => {
    // Load MCA 45-5-201 by default
    fetchStatute("45-5-201");
});

async function fetchStatute(statuteId) {
    try {
        const response = await fetch(`./data/${statuteId}.json`);
        if (!response.ok) {
            throw new Error(`Statute ${statuteId} not found.`);
        }
        
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
    sourceLink.href = data.source_url;

    // Render formatted subsections
    const container = document.getElementById("statute-subsections");
    container.innerHTML = ""; // Clear existing

    data.subsections.forEach(line => {
        const p = document.createElement("p");
        p.className = "subsection-item";
        
        // Add additional indent CSS if subsection starts with letter options like (a), (i)
        if (/^\([a-z]\)/i.test(line)) {
            p.classList.add("nested");
        }
        
        p.innerText = line;
        container.appendChild(p);
    });
}
