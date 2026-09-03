const POLL_INTERVAL = 15000;

const COLORS = {
    critical: "#ef4444",
    warning: "#f59e0b",
    accent: "#60a5fa",
    healthy: "#10b981",
    regional: "#f97316",
    muted: "#64748b",
    text: "#f1f5f9",
    textMuted: "#64748b",
    textDim: "#475569",
    border: "rgba(255,255,255,0.07)",
};

const WC_PALETTE = [
    "#f1f5f9",
    "#ef4444",
    "#f59e0b",
    "#60a5fa",
    "#94a3b8",
    "#10b981",
    "#a78bfa",
    "#f472b6",
];

let attackVectorChart = null;
let activeFilter = null;
let allNews = [];
let allIOCs = [];
let lastDataTime = null;
let pollCount = 0;
let inFlight = false;

document.addEventListener("DOMContentLoaded", () => {
    initClocks();
    initViewNav();
    initChart();
    initIOCSearch();
    pollData();
    setInterval(pollData, POLL_INTERVAL);
    setInterval(updateClocks, 1000);
    setInterval(updateFreshnessAge, 10000);
    document.getElementById("refresh-btn").addEventListener("click", () => {
        if (!inFlight) pollData();
    });
});

function initViewNav() {
    const tabs = document.querySelectorAll("#view-nav-bar .nav-tab");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            const viewId = tab.getAttribute("data-view");
            document.querySelectorAll(".soc-view-container").forEach(c => c.style.display = "none");
            const target = document.getElementById(viewId);
            if (target) {
                target.style.display = (viewId === "dashboard-grid") ? "grid" : "flex";
            }
            if (viewId === "ransomware-view") fetchRansomware();
            if (viewId === "apt-view") fetchThreatActors();
            if (viewId === "geo-view") fetchGeoEvents();
            if (viewId === "ioc-view") fetchIOCDesk();
        });
    });
}

function updateClocks() {
    const now = new Date();
    document.getElementById("clock-utc").textContent =
        now.toISOString().split("T")[1].split(".")[0];
    const gst = new Date(now.getTime() + 4 * 3600000);
    document.getElementById("clock-gst").textContent =
        gst.toISOString().split("T")[1].split(".")[0];
}

function initClocks() { updateClocks(); }

async function pollData() {
    if (inFlight) return;
    inFlight = true;

    const bar = document.getElementById("loading-bar");
    const barWrap = document.getElementById("loading-bar-wrap");
    const errBanner = document.getElementById("error-banner");

    if (pollCount === 0) {
        barWrap.style.display = "block";
        bar.style.width = "0%";
        setTimeout(() => { bar.style.width = "60%"; }, 50);
    }

    try {
        const resp = await fetch("/api/dashboard-data");
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        bar.style.width = "100%";
        setTimeout(() => { barWrap.style.display = "none"; bar.style.width = "0%"; }, 400);

        errBanner.style.display = "none";
        pollCount++;
        lastDataTime = data.last_updated ? new Date(data.last_updated) : new Date();
        renderDashboard(data);
    } catch (err) {
        console.error("Poll error:", err);
        barWrap.style.display = "none";
        errBanner.style.display = "flex";
        document.getElementById("error-text").textContent = `Connection issue — retrying in ${POLL_INTERVAL / 1000}s...`;
    } finally {
        inFlight = false;
    }
}

function handleVectorClick(vector) {
    if (activeFilter && activeFilter.type === "vector" && activeFilter.value === vector) {
        activeFilter = null;
    } else {
        activeFilter = { type: "vector", value: vector };
    }
    renderAttackVectors(window._lastVectors || {});
    renderNewsFeed(allNews);
}

function handleWordClick(word) {
    if (activeFilter && activeFilter.type === "keyword" && activeFilter.value === word) {
        activeFilter = null;
    } else {
        activeFilter = { type: "keyword", value: word };
    }
    renderNewsFeed(allNews);
}

function clearFilter() {
    activeFilter = null;
    renderAttackVectors(window._lastVectors || {});
    renderNewsFeed(allNews);
}

function renderDashboard(data) {
    window._lastVectors = data.attack_vectors || {};
    renderAttackVectors(window._lastVectors);
    renderKEV(data.kev || []);
    renderWordCloud(data.word_cloud || []);
    allNews = data.news || [];
    renderNewsFeed(allNews);
    renderPhishingDomains(data.phishing_domains || [], data.ioc_queue || []);
    renderOTXPulses(data.malware || [], data.malware_categorized || {});
    renderTicker(data.news || [], data.kev || []);
    renderPostureStrip(data);

    const totalStored = data.total_news_stored || 0;
    document.getElementById("db-stats").textContent = `DB: ${totalStored.toLocaleString()} articles`;
    const feedHealth = data.feed_health || {};
    const onlineCollectors = Object.values(feedHealth).filter(item => item.status === "ONLINE").length;
    const collectorCount = Object.keys(feedHealth).length;
    const ingestionStatus = document.getElementById("ingestion-status");
    ingestionStatus.classList.toggle("degraded", collectorCount > 0 && onlineCollectors < collectorCount);
    ingestionStatus.innerHTML =
        `<span class="pulse-dot"></span> INGESTION: ${onlineCollectors}/${collectorCount || 6} ONLINE`;

    if (data.last_updated) {
        const d = new Date(data.last_updated);
        document.getElementById("freshness-time").textContent =
            d.toISOString().split("T")[1].split(".")[0];
        updateFreshnessAge();
    }
}

function renderPostureStrip(data) {
    const posture = data.posture || {};
    const severity = posture.severity || {};
    const regional = data.regional_exposure || {};
    const health = data.feed_health || {};
    const coverage = data.attack_coverage || [];
    const online = Object.values(health).filter(item => item.status === "ONLINE").length;
    const total = Object.keys(health).length;
    const topTactics = coverage.filter(item => item.count > 0).slice(0, 3);

    document.getElementById("posture-summary").innerHTML = `
        <span class="posture-label">VULNERABILITY POSTURE</span>
        <span class="posture-value"><strong>${posture.total || 0}</strong> KEVs</span>
        <span class="posture-detail critical">${severity.critical || 0} critical</span>
        <span class="posture-detail">${posture.due_7d || 0} due 7d</span>`;
    document.getElementById("regional-summary").innerHTML = `
        <span class="posture-label">UAE / GCC WATCH</span>
        <span class="posture-value"><strong>${regional.regional_news || 0}</strong> regional signals</span>
        <span class="posture-detail">hosting metadata only</span>`;
    document.getElementById("coverage-summary").innerHTML = `
        <span class="posture-label">REPORTED ATT&amp;CK SIGNALS</span>
        <span class="coverage-bars">${topTactics.map(item => `<span title="${esc(item.tactic)}: ${item.count}"><i style="width:${Math.min(100, item.count * 12)}%"></i>${esc(item.tactic)}</span>`).join("") || "No classified signals"}</span>`;
    document.getElementById("feed-summary").innerHTML = `
        <span class="posture-label">FEED HEALTH</span>
        <span class="posture-value"><strong>${online}/${total || 6}</strong> collectors online</span>
        <span class="posture-detail">${getFreshnessLabel(data.last_updated)}</span>`;
}

function initChart() {
    const ctx = document.getElementById("chart-attack-vectors").getContext("2d");
    attackVectorChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: [],
            datasets: [{
                label: "Frequency %",
                data: [],
                backgroundColor: [],
                borderColor: [],
                borderWidth: 0,
                borderRadius: 3,
                borderSkipped: false,
            }],
        },
        options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { left: 0, right: 8, top: 0, bottom: 0 } },
            onClick: (event, elements) => {
                if (elements.length > 0) {
                    const label = attackVectorChart.data.labels[elements[0].index];
                    handleVectorClick(label);
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "#0e131f",
                    titleColor: COLORS.text,
                    bodyColor: COLORS.textMuted,
                    borderColor: COLORS.border,
                    borderWidth: 1,
                    titleFont: { family: "Inter", size: 11, weight: "600" },
                    bodyFont: { family: "JetBrains Mono", size: 10 },
                    padding: 6,
                    cornerRadius: 2,
                },
            },
            scales: {
                x: {
                    beginAtZero: true, max: 100,
                    grid: { color: "rgba(255,255,255,0.03)", drawTicks: false },
                    border: { display: false },
                    ticks: {
                        color: COLORS.textMuted,
                        font: { family: "JetBrains Mono", size: 8 },
                        padding: 4,
                        callback: v => v + "%",
                    },
                },
                y: {
                    grid: { display: false },
                    border: { display: false },
                    ticks: {
                        autoSkip: false,
                        color: COLORS.text,
                        font: { family: "Inter", size: 9, weight: "500" },
                        padding: 6,
                    },
                },
            },
        },
    });
}

function renderAttackVectors(vectors) {
    const sorted = Object.entries(vectors)
        .sort((a, b) => b[1] - a[1])
        .filter(([, v]) => v > 0)
        .slice(0, 5);
    if (!sorted.length) return;

    const labels = sorted.map(([k]) => k);
    const values = sorted.map(([, v]) => v);
    const barColors = values.map((v, i) => {
        const base = v > 15 ? COLORS.critical : v > 8 ? COLORS.warning : v > 3 ? COLORS.accent : COLORS.healthy;
        if (activeFilter && activeFilter.type === "vector") {
            return labels[i] === activeFilter.value ? base : base.replace(")", ",0.25)").replace("rgb", "rgba");
        }
        return base;
    });

    attackVectorChart.data.labels = labels;
    attackVectorChart.data.datasets[0].data = values;
    attackVectorChart.data.datasets[0].backgroundColor = barColors;
    attackVectorChart.data.datasets[0].borderColor = barColors;
    attackVectorChart.data.datasets[0].barThickness = 15;
    attackVectorChart.data.datasets[0].maxBarThickness = 15;
    attackVectorChart.update("none");
}

function cvssBadgeHTML(score) {
    if (score === null || score === undefined) {
        return '<span class="badge badge-low">CVSS N/A</span>';
    }
    let cls = "badge-low";
    let label = "";
    if (score >= 9.0) {
        cls = "badge-critical";
        label = `${score.toFixed(1)} CRIT`;
    } else if (score >= 7.0) {
        cls = "badge-high";
        label = `${score.toFixed(1)} HIGH`;
    } else if (score >= 4.0) {
        cls = "badge-medium";
        label = `${score.toFixed(1)} MED`;
    } else {
        cls = "badge-low";
        label = `${score.toFixed(1)}`;
    }
    return `<span class="badge ${cls}">${label}</span>`;
}

function renderKEV(kev) {
    const container = document.getElementById("kev-feed");
    if (!kev.length) {
        container.innerHTML = '<div class="loading-text">No KEV data</div>';
        return;
    }
    container.innerHTML = kev.slice(0, 6).map(item => {
        const dueDate = item.due_date ? new Date(`${item.due_date}T00:00:00Z`) : null;
        const overdue = dueDate && dueDate < new Date();
        const epssHtml = item.epss ? `<span class="badge badge-warning" title="${item.epss_percentile}% percentile">EPSS ${item.epss}%</span>` : "";
        return `
        <div class="kev-item">
            <div class="kev-details">
                <div class="kev-header">
                    <span class="kev-cve">${esc(item.cve_id || "N/A")}</span>
                    ${cvssBadgeHTML(item.cvss)}
                    ${epssHtml}
                </div>
                <div class="kev-info">
                    <span class="vendor">${esc(item.vendor)}</span> &mdash; ${esc(item.product)}: ${esc(item.vulnerability)}
                </div>
                <div class="kev-info" style="color:var(--text-dim)">
                    Added: ${esc(item.date_added)} &middot; <span class="${overdue ? "kev-overdue" : ""}">Due: ${esc(item.due_date || "N/A")}</span>
                </div>
            </div>
        </div>
    `;
    }).join("");
}

const WC_COLORS = [
    "#60a5fa", "#a78bfa", "#22d3ee", "#34d399",
    "#fbbf24", "#f472b6", "#fb923c", "#38bdf8",
];

function renderWordCloud(words) {
    const container = document.getElementById("wordcloud-container");
    if (!words || !words.length) {
        const svg = document.getElementById("wc-svg");
        if (svg) svg.innerHTML = '<text class="wc-empty" x="50%" y="50%">No trending keywords yet</text>';
        return;
    }
    initWordGraph({ nodes: words });
}

function initWordGraph(graph) {
    const svgEl = document.getElementById("wc-svg");
    if (!svgEl) return;

    const container = svgEl.parentElement;
    const rect = container.getBoundingClientRect();
    const W = rect.width;
    const H = rect.height;

    const svg = d3.select(svgEl)
        .attr("viewBox", `0 0 ${W} ${H}`)
        .attr("width", W)
        .attr("height", H);

    svg.selectAll("*").remove();

    const rawNodes = (graph.nodes || []).map((node) => {
        if (typeof node === "string") return { id: node, freq: 1, size: 1 };
        return {
            id: node.id || node.word || node.text || node.label,
            freq: Number(node.freq || node.weight || node.count || 1),
            // Use the backend's normalized score for ranking — it already
            // applies security-term boosts and tiered multipliers.  Falling
            // back to weight (article count) would re-sort by frequency and
            // undo the backend's specific-indicator prioritization.
            score: Number(node.normalized || node.score || 0),
            size: Number(node.size || node.normalized || node.weight || 1),
        };
    }).filter(node => node.id);

    if (!rawNodes.length) return;

    // Sort by backend score descending, then by freq as tiebreaker.
    // This preserves the backend's security-term prioritization.
    const maxScore = Math.max(...rawNodes.map(node => node.score || node.freq), 1);
    const maxKeywords = H < 190 ? 12 : H < 260 ? 16 : 20;
    const nodes = rawNodes
        .sort((a, b) => b.score - a.score || b.freq - a.freq)
        .slice(0, maxKeywords)
        .map((node, i) => ({
            ...node,
            rank: i + 1,
            color: WC_COLORS[i % WC_COLORS.length],
            importance: Math.max(0.18, (node.score || node.freq) / maxScore),
        }));

    const rowGap = 8;
    const wordGap = 10;
    const margin = 14;
    const maxRowW = W - margin * 2;
    const rows = [];
    let curRow = [];
    let curRowW = 0;

    for (const node of nodes) {
        node.fontSize = Math.round(10 + node.importance * 6);
        node.cardH = Math.round(24 + node.importance * 7);
        node.cardW = Math.min(maxRowW, Math.max(92, node.id.length * (node.fontSize * 0.61) + 54));
        const needed = curRowW === 0 ? node.cardW : node.cardW + wordGap;
        if (curRowW + needed > maxRowW && curRow.length > 0) {
            rows.push(curRow);
            curRow = [];
            curRowW = 0;
        }
        curRow.push(node);
        curRowW += curRow.length === 1 ? node.cardW : node.cardW + wordGap;
    }
    if (curRow.length) rows.push(curRow);

    let totalH = rows.reduce((sum, row) => {
        const rh = Math.max(...row.map(n => n.cardH));
        return sum + rh + rowGap;
    }, -rowGap);
    let yPos = Math.max(margin, (H - totalH) / 2);

    for (const row of rows) {
        const rowH = Math.max(...row.map(n => n.cardH));
        const rowTotalW = row.reduce((s, n) => s + n.cardW, 0) + (row.length - 1) * wordGap;
        let xPos = Math.max(margin, (W - rowTotalW) / 2);

        for (const node of row) {
            node.x = xPos;
            node.y = yPos + (rowH - node.cardH) / 2;
            xPos += node.cardW + wordGap;
        }
        yPos += rowH + rowGap;
    }

    const wordG = svg.append("g").attr("class", "wc-words");
    const wordSel = wordG.selectAll("g")
        .data(nodes)
        .enter()
        .append("g")
        .attr("class", "wc-chip")
        .attr("transform", d => `translate(${d.x}, ${d.y})`)
        .style("cursor", "pointer")
        .on("click", (event, d) => {
            event.stopPropagation();
            handleWordClick(d.id);
        })
        .on("mouseenter", function () {
            d3.select(this).classed("is-active", true);
        })
        .on("mouseleave", function () {
            d3.select(this).classed("is-active", false);
        });

    wordSel.append("rect")
        .attr("class", "wc-chip-bg")
        .attr("width", d => d.cardW)
        .attr("height", d => d.cardH)
        .attr("rx", 6)
        .attr("fill", d => d.color);
    wordSel.append("rect")
        .attr("class", "wc-chip-accent")
        .attr("width", 3)
        .attr("height", d => d.cardH - 10)
        .attr("x", 5)
        .attr("y", 5)
        .attr("rx", 1.5)
        .attr("fill", d => d.color);
    wordSel.append("text")
        .attr("class", "wc-word")
        .attr("x", 14)
        .attr("y", d => d.cardH / 2)
        .attr("font-size", d => d.fontSize)
        .text(d => d.id);
    wordSel.append("text")
        .attr("class", "wc-rank")
        .attr("x", d => d.cardW - 9)
        .attr("y", d => d.cardH / 2)
        .text(d => `${d.freq}`);
    wordSel.append("title").text(d => `${d.id}: ${d.freq} occurrence${d.freq === 1 ? "" : "s"} — click to filter news`);
}

function renderNewsFeed(news) {
    const container = document.getElementById("news-feed");
    if (!news.length) {
        container.innerHTML = '<div class="loading-text">No news data</div>';
        return;
    }

    let filtered = news;
    let filterLabel = "";
    if (activeFilter) {
        if (activeFilter.type === "vector") {
            filtered = news.filter(item => {
                const vecs = item.attack_vectors || [];
                return vecs.includes(activeFilter.value);
            });
            filterLabel = activeFilter.value;
        } else if (activeFilter.type === "keyword") {
            const kw = activeFilter.value.toLowerCase();
            filtered = news.filter(item => {
                const combined = ((item.title || "") + " " + (item.description || "")).toLowerCase();
                return combined.includes(kw);
            });
            filterLabel = `"${activeFilter.value}"`;
        }
    }

    let filterBar = "";
    if (activeFilter) {
        filterBar = `<div class="news-filter-bar"><span class="news-filter-label">FILTERED: ${esc(filterLabel)}</span><span class="news-filter-count">${filtered.length} of ${news.length}</span><span class="news-filter-clear" onclick="clearFilter()">&times;</span></div>`;
    }

    const sourceCounts = {};
    news.forEach(item => {
        const src = item.sourceBadge || item.source || "NEWS";
        sourceCounts[src] = (sourceCounts[src] || 0) + 1;
    });
    const countTags = Object.entries(sourceCounts)
        .sort((a, b) => b[1] - a[1])
        .map(([src, count]) => `<span class="news-source-count">${esc(src)}: ${count}</span>`)
        .join('<span class="news-source-sep">&middot;</span>');

    const displayItems = activeFilter ? filtered.slice(0, 10) : news.slice(0, 10);
    const itemsHtml = displayItems.map(item => {
        const cls = item.is_regional ? "regional" : "";
        const tags = [];
        if (item.is_regional) tags.push('<span class="badge badge-regional">MENA</span>');
        const badge = item.sourceBadge || item.source || "NEWS";
        tags.push(`<span class="badge badge-source">${esc(badge)}</span>`);
        const vectors = item.attack_vectors || [];
        vectors.forEach(v => {
            tags.push(`<span class="badge badge-vector">${esc(v)}</span>`);
        });
        return `
            <div class="news-item ${cls}">
                <div class="news-tags">${tags.join("")}</div>
                <div class="news-title">
                    <a href="${esc(item.link)}" target="_blank" rel="noopener">${esc(item.title)}</a>
                </div>
                <div class="news-meta">${esc(item.published)}</div>
            </div>
        `;
    }).join("");

    container.innerHTML = `${filterBar}<div class="news-source-bar">${countTags}</div>${itemsHtml}`;
}

function renderPhishingDomains(domains, iocs = []) {
    const container = document.getElementById("phish-domains");
    if (!domains.length) {
        container.innerHTML = '<div class="loading-text">No phishing data</div>';
        return;
    }
    const iocByDomain = new Map(iocs.filter(item => item.type === "domain").map(item => [item.value, item]));
    container.innerHTML = domains.slice(0, 10).map((item, i) => {
        const idx = String(i + 1).padStart(2, "0");
        return `
            <div class="phish-domain-row">
                <span class="phish-index">${idx}</span>
                <span class="phish-domain">${esc(item.domain)}</span>
                <span class="phish-meta">
                    <span class="phish-hits">${item.hits}</span>
                    ${item.country ? `<span class="phish-country">${esc(item.country)}</span>` : ""}
                    <button class="ioc-copy" title="Copy domain" onclick="copyIOC('${esc(item.domain)}')">COPY</button>
                </span>
            </div>
        `;
    }).join("");
}

async function copyIOC(value) {
    try {
        await navigator.clipboard.writeText(value);
    } catch (_) {
        window.prompt("Copy IOC", value);
    }
}

function renderOTXPulses(pulses, categorized) {
    const container = document.getElementById("otx-pulses");
    if (!pulses.length) {
        container.innerHTML = '<div class="loading-text">No OTX data</div>';
        return;
    }

    const order = ["Ransomware", "APT / Campaign", "Scam / Botnet", "Other"];
    let html = '<div class="otx-pulse-list">';

    for (const cat of order) {
        const items = categorized[cat];
        if (!items || !items.length) continue;
        html += `<div class="otx-category">${esc(cat)}</div>`;
        items.slice(0, 4).forEach(pulse => {
            html += `
                <div class="otx-pulse-row">
                    <span class="otx-pulse-name">${esc(pulse.name)}</span>
                    <div class="otx-pulse-meta">
                        <span class="badge badge-tlp">TLP:${esc(pulse.tlp)}</span>
                        ${pulse.date ? `<span class="badge badge-info">${esc(pulse.date)}</span>` : ""}
                    </div>
                </div>
            `;
        });
    }

    html += "</div>";
    container.innerHTML = html || '<div class="loading-text">No categorized pulses</div>';
}

function renderTicker(news, kev) {
    const items = [];
    kev.slice(0, 4).forEach(k => {
        const score = k.cvss ? ` CVSS ${k.cvss.toFixed(1)}` : "";
        items.push(`<span class="ticker-item ticker-kev">${esc(k.cve_id || "")}${score} &mdash; ${esc((k.vulnerability || "").substring(0, 80))}</span>`);
    });
    news.slice(0, 12).forEach(item => {
        const cls = item.is_regional ? "ticker-item ticker-uae" : "ticker-item";
        const badge = item.sourceBadge || item.source || "";
        items.push(`<span class="${cls}">[${esc(badge)}] ${esc(item.title.substring(0, 100))}</span>`);
    });
    const sep = '<span class="ticker-sep">|</span>';
    const joined = items.join(sep);
    document.getElementById("ticker-content").innerHTML = joined + sep + joined;
}

/* RANSOMWARE RADAR RENDERERS */
async function fetchRansomware() {
    try {
        const resp = await fetch("/api/ransomware");
        if (!resp.ok) return;
        const data = await resp.json();
        renderRansomware(data);
    } catch (err) {
        console.error("Ransomware fetch error:", err);
    }
}

function renderRansomware(data) {
    const listEl = document.getElementById("ransomware-list");
    const groupsEl = document.getElementById("ransomware-groups");
    const sectorsEl = document.getElementById("ransomware-sectors");

    const victims = data.victims || [];
    if (!victims.length) {
        listEl.innerHTML = '<div class="loading-text">No active ransomware victims logged</div>';
    } else {
        listEl.innerHTML = victims.map(v => `
            <div class="rw-item">
                <div class="rw-left">
                    <span class="rw-group">${esc(v.group_name)}</span>
                    <span class="rw-victim">${esc(v.victim_name)}</span>
                    <span class="rw-details">${esc(v.website || "No site")} ${v.sector ? "&middot; " + esc(v.sector) : ""}</span>
                </div>
                <div class="rw-right" style="text-align:right">
                    <span class="badge badge-critical">${esc(v.country || "GLOBAL")}</span>
                    <div class="rw-details" style="margin-top:4px">${esc(v.discovered_at)}</div>
                </div>
            </div>
        `).join("");
    }

    const topGroups = data.top_groups || [];
    groupsEl.innerHTML = topGroups.map(g => `
        <div class="rw-group-row">
            <span style="font-weight:700;color:var(--critical)">${esc(g.group)}</span>
            <span class="badge badge-critical">${g.count} victims</span>
        </div>
    `).join("") || '<div class="loading-text">No group metrics</div>';

    const topSectors = data.top_sectors || [];
    sectorsEl.innerHTML = topSectors.map(s => `
        <div class="country-row" style="margin-bottom:6px">
            <span style="min-width:110px;font-size:11px">${esc(s.sector)}</span>
            <div class="country-bar-bg">
                <div class="country-bar-fill" style="width:${Math.min(100, s.count * 15)}%;background:var(--accent)"></div>
            </div>
            <span style="font-weight:700">${s.count}</span>
        </div>
    `).join("") || '<div class="loading-text">No sector metrics</div>';
}

/* APT THREAT ACTORS RENDERERS */
async function fetchThreatActors() {
    try {
        const resp = await fetch("/api/threat-actors");
        if (!resp.ok) return;
        const data = await resp.json();
        renderThreatActors(data.actors || []);
    } catch (err) {
        console.error("APT fetch error:", err);
    }
}

function renderThreatActors(actors) {
    const gridEl = document.getElementById("apt-grid");
    if (!actors.length) {
        gridEl.innerHTML = '<div class="loading-text">No threat actor profiles available</div>';
        return;
    }
    gridEl.innerHTML = actors.map(a => `
        <div class="apt-card">
            <div class="apt-card-header">
                <div>
                    <span class="apt-name">${esc(a.flag || "🎯")} ${esc(a.name)}</span>
                    <div class="apt-origin">${esc(a.origin)} &middot; ${a.aliases ? esc(a.aliases.join(", ")) : ""}</div>
                </div>
                <span class="apt-status ${a.status === "ACTIVE" ? "active" : "monitoring"}">${a.status} (${a.mention_count})</span>
            </div>
            <div class="apt-desc">${esc(a.description)}</div>
            <div class="apt-meta">Targets: <span>${esc((a.target_sectors || []).join(", "))}</span></div>
            <div class="apt-meta">Regions: <span>${esc((a.target_regions || []).join(", "))}</span></div>
            ${a.recent_headlines && a.recent_headlines.length ? `
                <div class="apt-meta" style="margin-top:4px;border-top:1px dashed var(--border-faint);padding-top:4px">
                    Signal: <span style="color:var(--text-primary);font-style:italic">"${esc(a.recent_headlines[0])}"</span>
                </div>
            ` : ""}
        </div>
    `).join("");
}

/* GEO MAP RENDERERS */
async function fetchGeoEvents() {
    try {
        const resp = await fetch("/api/geo-events");
        if (!resp.ok) return;
        const data = await resp.json();
        renderGeoMap(data.events || []);
    } catch (err) {
        console.error("Geo fetch error:", err);
    }
}

function renderGeoMap(events) {
    const listEl = document.getElementById("geo-country-list");
    if (!events.length) {
        listEl.innerHTML = '<div class="loading-text">No geo event metrics available</div>';
    } else {
        const maxCount = Math.max(...events.map(e => e.count), 1);
        listEl.innerHTML = events.slice(0, 15).map(e => `
            <div class="country-row">
                <span style="min-width:110px;font-weight:600">${esc(e.country)}</span>
                <div class="country-bar-bg">
                    <div class="country-bar-fill" style="width:${Math.round((e.count / maxCount) * 100)}%"></div>
                </div>
                <span style="font-weight:700;color:var(--accent)">${e.count}</span>
            </div>
        `).join("");
    }

    // Render D3 SVG world map representation
    const svgEl = document.getElementById("geo-world-svg");
    if (!svgEl) return;
    const container = svgEl.parentElement;
    const W = container.clientWidth || 600;
    const H = container.clientHeight || 400;

    const svg = d3.select(svgEl)
        .attr("viewBox", `0 0 ${W} ${H}`)
        .attr("width", W)
        .attr("height", H);

    svg.selectAll("*").remove();

    // Subtle dark grid background for SOC radar feel
    const g = svg.append("g");
    
    // Outer grid rings / lines
    for (let x = 0; x < W; x += 40) {
        g.append("line").attr("x1", x).attr("y1", 0).attr("x2", x).attr("y2", H)
            .attr("stroke", "rgba(0, 240, 255, 0.05)").attr("stroke-width", 1);
    }
    for (let y = 0; y < H; y += 40) {
        g.append("line").attr("x1", 0).attr("y1", y).attr("x2", W).attr("y2", y)
            .attr("stroke", "rgba(0, 240, 255, 0.05)").attr("stroke-width", 1);
    }

    // Centered radar overlay text
    g.append("text").attr("x", W / 2).attr("y", 30)
        .attr("text-anchor", "middle").attr("fill", "var(--text-dim)")
        .attr("font-family", "JetBrains Mono").attr("font-size", "11px")
        .text("GLOBAL CYBER EVENT RADAR - LIVE GEOGRAPHIC THREAT METRICS");

    // Coordinates for key countries
    const coords = {
        "United States": [W * 0.25, H * 0.38],
        "United Arab Emirates": [W * 0.62, H * 0.48],
        "Saudi Arabia": [W * 0.59, H * 0.49],
        "United Kingdom": [W * 0.46, H * 0.28],
        "Germany": [W * 0.50, H * 0.29],
        "France": [W * 0.48, H * 0.32],
        "Russia": [W * 0.70, H * 0.25],
        "Ukraine": [W * 0.56, H * 0.31],
        "China": [W * 0.76, H * 0.38],
        "India": [W * 0.68, H * 0.47],
        "Japan": [W * 0.85, H * 0.37],
        "Australia": [W * 0.84, H * 0.72],
        "Canada": [W * 0.24, H * 0.22],
        "Israel": [W * 0.56, H * 0.44],
        "Iran": [W * 0.61, H * 0.43],
    };

    events.forEach(e => {
        const pt = coords[e.country];
        if (pt) {
            const nodeG = g.append("g").attr("transform", `translate(${pt[0]}, ${pt[1]})`);
            const radius = Math.min(24, Math.max(6, e.count * 2.5));
            nodeG.append("circle")
                .attr("r", radius)
                .attr("fill", "rgba(0, 240, 255, 0.15)")
                .attr("stroke", "#00f0ff")
                .attr("stroke-width", 1.5);
            nodeG.append("circle")
                .attr("r", radius * 0.4)
                .attr("fill", "#00f0ff");
            nodeG.append("text")
                .attr("y", radius + 12)
                .attr("text-anchor", "middle")
                .attr("fill", "var(--text-primary)")
                .attr("font-family", "JetBrains Mono")
                .attr("font-size", "9px")
                .attr("font-weight", "700")
                .text(`${e.country} (${e.count})`);
        }
    });
}

/* ACTIONABLE IOC DESK RENDERERS */
async function fetchIOCDesk() {
    try {
        const resp = await fetch("/api/iocs");
        if (!resp.ok) return;
        const data = await resp.json();
        allIOCs = data.items || [];
        renderIOCDesk(allIOCs);
    } catch (err) {
        console.error("IOC desk fetch error:", err);
    }
}

function initIOCSearch() {
    const input = document.getElementById("ioc-search-input");
    const filterSelect = document.getElementById("ioc-type-filter");
    const handler = () => {
        const query = (input.value || "").toLowerCase();
        const selectedType = filterSelect.value;
        const filtered = allIOCs.filter(item => {
            const itype = (item.type || item.ioc_type || "").toLowerCase();
            const ival = (item.value || item.ioc_value || "").toLowerCase();
            const isrc = (item.source || item.reporter || "").toLowerCase();
            const matchesQuery = !query || ival.includes(query) || isrc.includes(query) || itype.includes(query);
            const matchesType = !selectedType || itype === selectedType;
            return matchesQuery && matchesType;
        });
        renderIOCDesk(filtered);
    };
    if (input) input.addEventListener("input", handler);
    if (filterSelect) filterSelect.addEventListener("change", handler);
}

function renderIOCDesk(iocs) {
    const tbody = document.getElementById("ioc-table-body");
    if (!iocs || !iocs.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="loading-text">No matching IOCs found</td></tr>';
        return;
    }
    tbody.innerHTML = iocs.map(item => {
        const itype = item.type || item.ioc_type || "domain";
        const ival = item.value || item.ioc_value || "";
        const threat = item.threat_type || item.malware_family || "Suspicious / Phishing";
        const country = item.country || "Global";
        const source = item.source || item.reporter || "OSINT";
        const firstSeen = item.first_seen || "Recent";
        return `
            <tr>
                <td><span class="badge badge-source">${esc(itype.toUpperCase())}</span></td>
                <td>
                    <span style="font-weight:600">${esc(ival)}</span>
                    <button class="ioc-copy" style="margin-left:6px" onclick="copyIOC('${esc(ival)}')">COPY</button>
                </td>
                <td><span class="badge badge-critical">${esc(threat)}</span></td>
                <td>${esc(country)}</td>
                <td>${esc(source)}</td>
                <td>${esc(firstSeen)}</td>
            </tr>
        `;
    }).join("");
}

function esc(text) {
    if (!text) return "";
    const m = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
    return String(text).replace(/[&<>"']/g, c => m[c]);
}

function getFreshnessLabel(isoStr) {
    if (!isoStr) return "No data yet";
    const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000);
    if (diff < 60) return "Updated just now";
    if (diff < 3600) return `Updated ${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `Updated ${Math.floor(diff / 3600)}h ago`;
    return `Updated ${Math.floor(diff / 86400)}d ago`;
}

function updateFreshnessAge() {
    const el = document.getElementById("freshness-age");
    if (!el || !lastDataTime) return;
    const diff = Math.floor((Date.now() - lastDataTime.getTime()) / 1000);
    let label, cls;
    if (diff < 300) { label = "Fresh"; cls = "fresh"; }
    else if (diff < 900) { label = `${Math.floor(diff / 60)}m old`; cls = "ok"; }
    else if (diff < 1800) { label = `${Math.floor(diff / 60)}m old`; cls = "stale"; }
    else { label = `${Math.floor(diff / 60)}m old`; cls = "very-stale"; }
    el.textContent = label;
    el.className = "freshness-age " + cls;
}

/* ========== DIAGNOSTICS MODAL ========== */

function initDiagnostics() {
    const btn = document.getElementById("diag-btn");
    const overlay = document.getElementById("diag-overlay");
    const closeBtn = document.getElementById("diag-close");
    const runBtn = document.getElementById("diag-run-btn");

    if (btn) btn.addEventListener("click", openDiagnostics);
    if (closeBtn) closeBtn.addEventListener("click", closeDiagnostics);
    if (runBtn) runBtn.addEventListener("click", () => fetchDiagnostics());
    if (overlay) overlay.addEventListener("click", (e) => {
        if (e.target === overlay) closeDiagnostics();
    });
}

function openDiagnostics() {
    document.getElementById("diag-overlay").style.display = "flex";
    fetchDiagnostics();
}

function closeDiagnostics() {
    document.getElementById("diag-overlay").style.display = "none";
}

async function fetchDiagnostics() {
    const body = document.getElementById("diag-modal-body");
    const runBtn = document.getElementById("diag-run-btn");
    body.innerHTML = '<div class="diag-loading">&#8987; Running health checks — this may take a few seconds...</div>';
    runBtn.disabled = true;
    runBtn.textContent = "Running...";

    try {
        const resp = await fetch("/api/diagnostics");
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        renderDiagnostics(data);
    } catch (err) {
        body.innerHTML = `<div class="diag-section diag-error">
            <div class="diag-section-title">Connection Error</div>
            <p>Failed to fetch diagnostics: ${esc(err.message)}</p>
            <p>Ensure the backend is running and reachable.</p>
        </div>`;
    } finally {
        runBtn.disabled = false;
        runBtn.innerHTML = "&#8635; Run Health Check";
    }
}

function diagStatusIcon(status) {
    if (status === "ok" || status === "online" || status === true) return '<span class="diag-dot diag-dot-ok"></span>';
    if (status === "warning" || status === "degraded") return '<span class="diag-dot diag-dot-warn"></span>';
    return '<span class="diag-dot diag-dot-err"></span>';
}

function renderDiagnostics(data) {
    const body = document.getElementById("diag-modal-body");
    let html = "";

    // System Health
    const sys = data.system || {};
    html += `<div class="diag-section">
        <div class="diag-section-title">${diagStatusIcon(sys.status)} System Health</div>
        <div class="diag-grid">
            <div class="diag-kv"><span class="diag-k">Uptime</span><span class="diag-v">${esc(sys.uptime_human || "N/A")}</span></div>
            <div class="diag-kv"><span class="diag-k">RAM</span><span class="diag-v">${sys.ram_mb || 0} MB</span></div>
            <div class="diag-kv"><span class="diag-k">CPU Load (1m)</span><span class="diag-v">${sys.cpu_load_1m || 0}</span></div>
            <div class="diag-kv"><span class="diag-k">CPU Load (5m)</span><span class="diag-v">${sys.cpu_load_5m || 0}</span></div>
            <div class="diag-kv"><span class="diag-k">Active Threads</span><span class="diag-v">${sys.active_threads || 0}</span></div>
            <div class="diag-kv"><span class="diag-k">Gunicorn</span><span class="diag-v">${esc(sys.gunicorn_config || "N/A")}</span></div>
            <div class="diag-kv"><span class="diag-k">Python</span><span class="diag-v">${esc(sys.python_version || "N/A")}</span></div>
            <div class="diag-kv"><span class="diag-k">PID</span><span class="diag-v">${sys.pid || "N/A"}</span></div>
        </div>
    </div>`;

    // Database Health
    const db = data.database || {};
    html += `<div class="diag-section">
        <div class="diag-section-title">${diagStatusIcon(db.status)} Database Health</div>
        <div class="diag-grid">
            <div class="diag-kv"><span class="diag-k">File Size</span><span class="diag-v">${db.file_size_mb || 0} MB</span></div>
            <div class="diag-kv"><span class="diag-k">WAL Size</span><span class="diag-v">${db.wal_size_mb || 0} MB</span></div>
            <div class="diag-kv"><span class="diag-k">Path</span><span class="diag-v diag-path">${esc(db.file_path || "N/A")}</span></div>
        </div>
        <div class="diag-checks">`;
    (db.checks || []).forEach(c => {
        html += `<div class="diag-check ${c.status === "ok" ? "" : c.status === "warning" ? "diag-check-warn" : "diag-check-err"}">
            <span class="diag-check-name">${diagStatusIcon(c.status)} ${esc(c.name)}</span>
            <span class="diag-check-detail">${esc(c.detail || "")}</span>
        </div>`;
    });
    html += `</div></div>`;

    // Table counts
    if (db.table_counts) {
        html += `<div class="diag-section">
            <div class="diag-section-title">&#128202; Table Row Counts</div>
            <div class="diag-grid diag-grid-compact">`;
        Object.entries(db.table_counts).forEach(([tbl, cnt]) => {
            html += `<div class="diag-kv"><span class="diag-k">${esc(tbl)}</span><span class="diag-v">${cnt >= 0 ? cnt.toLocaleString() : "ERR"}</span></div>`;
        });
        html += `</div></div>`;
    }

    // External Connectivity
    const conn = data.connectivity || {};
    html += `<div class="diag-section">
        <div class="diag-section-title">${diagStatusIcon(conn.status)} External Connectivity (${conn.online_count || 0}/${conn.total || 0} online)</div>
        <div class="diag-checks">`;
    (conn.targets || []).forEach(t => {
        html += `<div class="diag-check ${t.online ? "" : "diag-check-err"}">
            <span class="diag-check-name">${diagStatusIcon(t.online)} ${esc(t.name)}</span>
            <span class="diag-check-detail">${esc(t.status || "")}</span>
        </div>`;
    });
    html += `</div></div>`;

    // Scheduler Status
    const sched = data.scheduler || {};
    html += `<div class="diag-section">
        <div class="diag-section-title">${diagStatusIcon(sched.status)} Scheduler & Collectors</div>
        <div class="diag-checks">`;
    (sched.collectors || []).forEach(c => {
        const statusCls = c.status === "ONLINE" ? "" : c.status === "DEGRADED" ? "diag-check-warn" : "diag-check-err";
        html += `<div class="diag-check ${statusCls}">
            <span class="diag-check-name">${diagStatusIcon(c.status === "ONLINE")} ${esc(c.name)}</span>
            <span class="diag-check-detail">
                ${esc(c.status)} | Every ${esc(c.interval_human)} | Last: ${c.age_seconds !== null ? c.age_seconds + "s ago" : "never"}
                ${c.latency_ms ? ` | ${c.latency_ms}ms` : ""}
                ${c.error ? ` | <span class="diag-err-text">${esc(c.error)}</span>` : ""}
            </span>
        </div>`;
    });
    html += `</div></div>`;

    // Source Status
    const sources = data.sources || {};
    if (Object.keys(sources).length) {
        html += `<div class="diag-section">
            <div class="diag-section-title">&#128225; Feed Source Status</div>
            <div class="diag-checks">`;
        Object.entries(sources).forEach(([key, info]) => {
            html += `<div class="diag-check ${info.online ? "" : "diag-check-err"}">
                <span class="diag-check-name">${diagStatusIcon(info.online)} ${esc(key)}</span>
                <span class="diag-check-detail">${esc(info.status || "UNKNOWN")} | ${info.count || 0} items</span>
            </div>`;
        });
        html += `</div></div>`;
    }

    html += `<div class="diag-timestamp">Last checked: ${esc(data.timestamp || new Date().toISOString())}</div>`;
    body.innerHTML = html;
}

document.addEventListener("DOMContentLoaded", initDiagnostics);
