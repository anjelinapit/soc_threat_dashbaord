let currentPage = 1;
let allVectors = [];

document.addEventListener("DOMContentLoaded", () => {
    loadArticles();
    loadSources();
    loadStopWords();
    loadVectorKeywords();

    document.getElementById("search-input").addEventListener("input", debounce(() => { currentPage = 1; loadArticles(); }, 300));
    document.getElementById("filter-source").addEventListener("change", () => { currentPage = 1; loadArticles(); });
    document.getElementById("filter-vector").addEventListener("change", () => { currentPage = 1; loadArticles(); });

    document.getElementById("add-stop-word-btn").addEventListener("click", addStopWord);
    document.getElementById("stop-word-input").addEventListener("keydown", e => { if (e.key === "Enter") addStopWord(); });

    document.getElementById("modal-close").addEventListener("click", closeModal);
    document.getElementById("modal-cancel").addEventListener("click", closeModal);
    document.getElementById("modal-save").addEventListener("click", saveVectors);
    document.getElementById("modal-overlay").addEventListener("click", e => { if (e.target === e.currentTarget) closeModal(); });

    document.getElementById("vector-modal-close").addEventListener("click", closeVectorModal);
    document.getElementById("vector-modal-cancel").addEventListener("click", closeVectorModal);
    document.getElementById("vector-modal-save").addEventListener("click", saveVectorKeywords);
    document.getElementById("vector-modal-overlay").addEventListener("click", e => { if (e.target === e.currentTarget) closeVectorModal(); });

    document.getElementById("add-vector-btn").addEventListener("click", openAddVectorModal);
    document.getElementById("vector-name-input").addEventListener("keydown", e => { if (e.key === "Enter") openAddVectorModal(); });
    document.getElementById("add-vector-modal-save").addEventListener("click", saveNewVector);
    document.getElementById("add-vector-modal-cancel").addEventListener("click", closeAddVectorModal);
    document.getElementById("add-vector-modal-close").addEventListener("click", closeAddVectorModal);
    document.getElementById("add-vector-modal-overlay").addEventListener("click", e => { if (e.target === e.currentTarget) closeAddVectorModal(); });
});

async function loadArticles() {
    const search = document.getElementById("search-input").value;
    const source = document.getElementById("filter-source").value;
    const vector = document.getElementById("filter-vector").value;

    try {
        const params = new URLSearchParams({ page: currentPage, per_page: 20 });
        if (search) params.set("search", search);
        if (source) params.set("source", source);
        if (vector) params.set("vector", vector);

        const resp = await fetch(`/api/articles?${params}`);
        const data = await resp.json();

        document.getElementById("db-total").textContent = `${data.total.toLocaleString()} articles`;
        document.getElementById("article-count").textContent = `${data.total} articles (page ${data.page}/${data.pages})`;

        renderArticleTable(data.articles);
        renderPagination(data.page, data.pages);
    } catch (err) {
        console.error("Load articles error:", err);
        document.getElementById("article-table-wrap").innerHTML = '<div class="loading-text">Error loading articles</div>';
    }
}

function renderArticleTable(articles) {
    const wrap = document.getElementById("article-table-wrap");
    if (!articles.length) {
        wrap.innerHTML = '<div class="loading-text">No articles found</div>';
        return;
    }

    let html = '<table class="article-table"><thead><tr>';
    html += '<th class="at-date">DATE</th>';
    html += '<th class="at-source">SOURCE</th>';
    html += '<th class="at-title">TITLE</th>';
    html += '<th class="at-vectors">VECTORS</th>';
    html += '<th class="at-action">ACTION</th>';
    html += '</tr></thead><tbody>';

    for (const item of articles) {
        const date = (item.fetched_at || "").substring(0, 10);
        const badge = item.source_badge || "NEWS";
        const vectors = (item.attack_vectors || []).map(v =>
            `<span class="badge badge-vector">${esc(v)}</span>`
        ).join(" ");

        html += `<tr>
            <td class="at-date">${esc(date)}</td>
            <td class="at-source"><span class="badge badge-source">${esc(badge)}</span></td>
            <td class="at-title" title="${esc(item.title)}">${esc(item.title)}</td>
            <td class="at-vectors">${vectors || '<span class="at-none">none</span>'}</td>
            <td class="at-action"><button class="reclassify-btn" onclick="openReclassifyModal(${item.id}, '${esc(item.title).replace(/'/g, "\\'")}')">Reclassify</button></td>
        </tr>`;
    }

    html += '</tbody></table>';
    wrap.innerHTML = html;
}

function renderPagination(page, pages) {
    const container = document.getElementById("pagination");
    if (pages <= 1) { container.innerHTML = ""; return; }

    let html = "";
    html += `<button class="page-btn" ${page <= 1 ? "disabled" : ""} onclick="goToPage(${page - 1})">&laquo; Prev</button>`;
    html += `<span class="page-info">Page ${page} of ${pages}</span>`;
    html += `<button class="page-btn" ${page >= pages ? "disabled" : ""} onclick="goToPage(${page + 1})">Next &raquo;</button>`;
    container.innerHTML = html;
}

function goToPage(page) {
    currentPage = page;
    loadArticles();
}

async function loadSources() {
    try {
        const resp = await fetch("/api/sources");
        const sources = await resp.json();
        const select = document.getElementById("filter-source");
        for (const src of sources) {
            const opt = document.createElement("option");
            opt.value = src;
            opt.textContent = src;
            select.appendChild(opt);
        }

        const vecSelect = document.getElementById("filter-vector");
        const vResp = await fetch("/api/attack-vector-keywords");
        const vData = await vResp.json();
        const vectors = Object.keys(vData);
        for (const vec of vectors) {
            const opt = document.createElement("option");
            opt.value = vec;
            opt.textContent = vec;
            vecSelect.appendChild(opt);
        }
    } catch (err) {
        console.error("Load sources error:", err);
    }
}

let currentArticleId = null;

function openReclassifyModal(articleId, title) {
    currentArticleId = articleId;
    document.getElementById("modal-article-title").textContent = title;

    const container = document.getElementById("modal-vectors");
    container.innerHTML = "";

    fetch("/api/attack-vector-keywords")
        .then(r => r.json())
        .then(vData => {
            const vectors = Object.keys(vData);
            for (const vec of vectors) {
                const label = document.createElement("label");
                label.className = "modal-checkbox";
                const cb = document.createElement("input");
                cb.type = "checkbox";
                cb.value = vec;
                cb.className = "vector-cb";
                label.appendChild(cb);
                label.appendChild(document.createTextNode(vec));
                container.appendChild(label);
            }

            return fetch(`/api/articles/${articleId}`);
        })
        .then(r => r.json())
        .then(data => {
            const existing = data.attack_vectors || [];
            document.querySelectorAll(".vector-cb").forEach(cb => {
                cb.checked = existing.includes(cb.value);
            });
        });

    document.getElementById("modal-overlay").style.display = "flex";
}

function closeModal() {
    document.getElementById("modal-overlay").style.display = "none";
    currentArticleId = null;
}

async function saveVectors() {
    if (!currentArticleId) return;
    const vectors = [];
    document.querySelectorAll(".vector-cb:checked").forEach(cb => vectors.push(cb.value));
    try {
        await fetch(`/api/articles/${currentArticleId}/vectors`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ vectors }),
        });
        closeModal();
        loadArticles();
    } catch (err) {
        console.error("Save vectors error:", err);
    }
}

async function loadStopWords() {
    try {
        const resp = await fetch("/api/stop-words");
        const words = await resp.json();
        renderStopWords(words);
    } catch (err) {
        console.error("Load stop words error:", err);
    }
}

function renderStopWords(words) {
    const container = document.getElementById("stop-words-list");
    if (!words.length) {
        container.innerHTML = '<div class="loading-text">No stop words</div>';
        return;
    }
    container.innerHTML = words.map(w =>
        `<span class="stop-word-tag">${esc(w)}<span class="sw-remove" onclick="removeStopWord('${esc(w).replace(/'/g, "\\'")}')">&times;</span></span>`
    ).join("");
}

async function addStopWord() {
    const input = document.getElementById("stop-word-input");
    const word = input.value.trim();
    if (!word) return;
    try {
        await fetch("/api/stop-words", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ word }),
        });
        input.value = "";
        loadStopWords();
    } catch (err) {
        console.error("Add stop word error:", err);
    }
}

async function removeStopWord(word) {
    try {
        await fetch(`/api/stop-words/${encodeURIComponent(word)}`, { method: "DELETE" });
        loadStopWords();
    } catch (err) {
        console.error("Remove stop word error:", err);
    }
}

async function loadVectorKeywords() {
    try {
        const resp = await fetch("/api/attack-vector-keywords");
        const data = await resp.json();
        allVectors = Object.keys(data);
        renderVectorKeywords(data);
    } catch (err) {
        console.error("Load vector keywords error:", err);
    }
}

function renderVectorKeywords(data) {
    const container = document.getElementById("vector-keywords-list");
    const entries = Object.entries(data);
    if (!entries.length) {
        container.innerHTML = '<div class="loading-text">No vector keywords</div>';
        return;
    }
    container.innerHTML = entries.map(([vector, keywords]) => {
        const kwDisplay = keywords.slice(0, 4).join(", ") + (keywords.length > 4 ? ` +${keywords.length - 4}` : "");
        return `
            <div class="vk-row">
                <div class="vk-vector">${esc(vector)}</div>
                <div class="vk-keywords">${esc(kwDisplay)}</div>
                <button class="vk-edit" onclick="openVectorModal('${esc(vector).replace(/'/g, "\\'")}', '${esc(JSON.stringify(keywords)).replace(/'/g, "\\'")}')">Edit</button>
                <button class="vk-delete" onclick="deleteVector('${esc(vector).replace(/'/g, "\\'")}')">&times;</button>
            </div>
        `;
    }).join("");
}

function openVectorModal(vector, keywordsJson) {
    document.getElementById("vector-modal-title").textContent = `EDIT: ${vector}`;
    document.getElementById("vector-modal-textarea").value = JSON.parse(keywordsJson || "[]").join("\n");
    document.getElementById("vector-modal-overlay").dataset.vector = vector;
    document.getElementById("vector-modal-overlay").style.display = "flex";
}

function closeVectorModal() {
    document.getElementById("vector-modal-overlay").style.display = "none";
}

async function saveVectorKeywords() {
    const vector = document.getElementById("vector-modal-overlay").dataset.vector;
    const raw = document.getElementById("vector-modal-textarea").value;
    const keywords = raw.split("\n").map(s => s.trim()).filter(s => s);
    try {
        await fetch(`/api/attack-vector-keywords/${encodeURIComponent(vector)}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ keywords }),
        });
        closeVectorModal();
        loadVectorKeywords();
        loadSources();
    } catch (err) {
        console.error("Save vector keywords error:", err);
    }
}

async function deleteVector(vector) {
    if (!confirm(`Delete vector "${vector}"? This cannot be undone.`)) return;
    try {
        await fetch(`/api/attack-vector-keywords/${encodeURIComponent(vector)}`, { method: "DELETE" });
        loadVectorKeywords();
        loadSources();
    } catch (err) {
        console.error("Delete vector error:", err);
    }
}

function openAddVectorModal() {
    document.getElementById("add-vector-name").value = "";
    document.getElementById("add-vector-keywords").value = "";
    document.getElementById("add-vector-modal-overlay").style.display = "flex";
}

function closeAddVectorModal() {
    document.getElementById("add-vector-modal-overlay").style.display = "none";
}

async function saveNewVector() {
    const name = document.getElementById("add-vector-name").value.trim();
    const raw = document.getElementById("add-vector-keywords").value;
    const keywords = raw.split("\n").map(s => s.trim()).filter(s => s);
    if (!name) { alert("Vector name is required."); return; }
    try {
        await fetch("/api/attack-vector-keywords", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ vector: name, keywords }),
        });
        closeAddVectorModal();
        loadVectorKeywords();
        loadSources();
    } catch (err) {
        console.error("Add vector error:", err);
    }
}

function esc(text) {
    if (!text) return "";
    const m = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
    return String(text).replace(/[&<>"']/g, c => m[c]);
}

function debounce(fn, delay) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}
