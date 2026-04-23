let playerParty = null;

const state = {
    districtStatus: {},
    current: [],
    finalized: [],
    electionToAssemblyWinner: {},
    totalAssigned: 0,
};

const map = L.map('map', {
    center: [40.7128, -74.0060],
    zoom: 11,
    minZoom: 10,
    maxBounds: [[40.4, -74.35], [40.95, -73.65]],
});

L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; CartoDB',
    subdomains: 'abcd',
    maxZoom: 19
}).addTo(map);

const layerMap = {};

const PARTY_COLORS = {
    DEM: '#007bff',
    REP: '#dc3545',
    BLK: '#28a745',
    WEP: '#6f42c1',
    IND: '#fd7e14',
    CON: '#e83e8c',
    GRE: '#20c997',
    WOR: '#856404',
    OTH: '#6c757d',
};

function getStyle(id, feature = null) {
    const status = state.districtStatus[id] || 'unassigned';

    // Use the passed-in GeoJSON feature first
    // Fall back to the stored layer feature later if needed
    const actualFeature = feature || (layerMap[id] && layerMap[id].feature);
    const party = (actualFeature && actualFeature.properties.party) || 'OTH';

    if (status === 'unassigned') {
        return {
            fillColor: PARTY_COLORS[party] || '#6c757d',
            fillOpacity: 0.35,
            color: '#adb5bd',
            weight: 0.5
        };
    }
    if (status === 'inprogress') {
        return {
            fillColor: '#ffc107',
            fillOpacity: 0.6,
            color: '#ffc107',
            weight: 2
        };
    }
    if (status === 'neighbor') {
        return {
            fillColor: '#ffffff',
            fillOpacity: 0.5,
            color: '#6c757d',
            weight: 1,
            dashArray: '4 3'
        };
    }
    if (status === 'finalized') {
        const winner = state.electionToAssemblyWinner[id] || 'OTH';
        return {
            fillColor: PARTY_COLORS[winner] || '#6c757d',
            fillOpacity: 0.8,
            color: '#343a40',
            weight: 0.5
        };
    }
    return {
        fillColor: '#e9ecef',
        fillOpacity: 0.3,
        color: '#ced4da',
        weight: 0.5
    };
}

function initMap() {
    ELECTION_GEOJSON.features.forEach(f => {
        state.districtStatus[parseInt(f.properties.ElectDist)] = 'unassigned';
    });

    L.geoJSON(ELECTION_GEOJSON, {
        style: f => getStyle(parseInt(f.properties.ElectDist), f),
        onEachFeature: (feature, layer) => {
            const id = parseInt(feature.properties.ElectDist);
            layerMap[id] = layer;
            layer.feature = feature;
            layer.on('click', () => onDistrictClick(id));
            layer.on('mouseover', () => {
                const s = state.districtStatus[id];
                if (s === 'unassigned' || s === 'neighbor') {
                    layer.setStyle({ weight: 2, color: '#343a40' });
                }
            });
            layer.on('mouseout', () => layer.setStyle(getStyle(id)));
        }
    }).addTo(map);

    document.getElementById('header-total').textContent = TOTAL_DISTRICTS;

    setTimeout(() => { map.invalidateSize(); }, 500);
}
// ================================================================
function startGame(party) {
    playerParty = party;
    $('#startModal').modal('hide');
    document.getElementById('header-party-badge').textContent = party;
    document.getElementById('header-party-badge').className = `badge badge-${party === 'DEM' ? 'primary' : 'danger'}`;
    updateCurrentDistrictNum();
    setMessage(`Playing as ${party}. Click any election district to start.`, 'alert-info');
}

function loadSavedMap(mapId) {
    const saved = SAVED_MAPS.find(m => m.map_id === parseInt(LOAD_MAP_ID));
    if (!saved) return;

    playerParty = saved.player_party || 'DEM';
    const districtsToLoad = saved.assembly_districts.slice(0, MAX_ASSEMBLY);

    $('#startModal').modal('hide');
    document.getElementById('header-party-badge').textContent = playerParty;
    document.getElementById('header-party-badge').className = `badge badge-${playerParty === 'DEM' ? 'primary' : 'danger'}`;

    saved.assembly_districts.forEach(ad => {
        let totals = {};
        ad.electionDistricts.forEach(eid => {
            const counts = (VOTER_COUNTS[String(eid)] || {}).counts || {};
            Object.entries(counts).forEach(([p, c]) => {
                totals[p] = (totals[p] || 0) + c;
            });
        });
        const winner = Object.keys(totals).length
            ? Object.keys(totals).reduce((a, b) => totals[a] > totals[b] ? a : b)
            : 'OTH';

        state.finalized.push({
            id: ad.id,
            electionDistricts: ad.electionDistricts,
            winner
        });

        ad.electionDistricts.forEach(eid => {
            const id = parseInt(eid);
            state.districtStatus[id] = 'finalized';
            state.electionToAssemblyWinner[id] = winner;
            layerMap[id] && layerMap[id].setStyle(getStyle(id));
        });

        state.totalAssigned += ad.electionDistricts.length;
    });

    updateProgress();
    updateDistrictList();
    updateCurrentDistrictNum();
    setMessage(`Loaded map: ${saved.map_name}`, 'alert-success');

    if (state.finalized.length === MAX_ASSEMBLY) {
        setTimeout(showFinalScore, 400);
    }
}

function onDistrictClick(id) {
    if (!playerParty) return;

    const status = state.districtStatus[id];

    if (status === 'finalized') {
        setMessage('That district is already finalized.', 'alert-danger');
        return;
    }

    if (state.current.length === 0) {
        if (status !== 'unassigned') return;
        addToCurrent(id);
        return;
    }

    if (status === 'inprogress') {
        tryRemoveFromCurrent(id);
        return;
    }

    if (status !== 'neighbor') {
        setMessage('You can only add adjacent districts.', 'alert-warning');
        return;
    }

    addToCurrent(id);
}

function addToCurrent(id) {
    state.current.push(id);
    state.districtStatus[id] = 'inprogress';
    layerMap[id] && layerMap[id].setStyle(getStyle(id));
    updateNeighbors();
    updateCurrentStats();
    updateFinalizeButton();
    setMessage(`Added district ${id}. Selection: ${state.current.length} election district(s).`, 'alert-success');
}

function tryRemoveFromCurrent(id) {
    if (state.current.length === 1) {
        state.districtStatus[id] = 'unassigned';
        state.current = [];
        layerMap[id] && layerMap[id].setStyle(getStyle(id));
        updateNeighbors();
        updateCurrentStats();
        updateFinalizeButton();
        setMessage('Selection cleared.', 'alert-info');
        return;
    }

    const remaining = state.current.filter(x => x !== id);
    if (isContiguousClient(remaining)) {
        state.current = remaining;
        state.districtStatus[id] = 'unassigned';
        layerMap[id] && layerMap[id].setStyle(getStyle(id));
        updateNeighbors();
        updateCurrentStats();
        updateFinalizeButton();
        setMessage(`Removed district ${id}.`, 'alert-info');
    } else {
        setMessage('Cannot remove — would break contiguity.', 'alert-danger');
    }
}

function isContiguousClient(ids) {
    if (ids.length <= 1) return true;
    const set = new Set(ids.map(String));
    const visited = new Set();
    const queue = [String(ids[0])];
    visited.add(String(ids[0]));
    while (queue.length) {
        const cur = queue.shift();
        (ADJACENCY_MAP[cur] || []).forEach(n => {
            if (set.has(n) && !visited.has(n)) { visited.add(n); queue.push(n); }
        });
    }
    return visited.size === ids.length;
}

function updateNeighbors() {
    Object.keys(state.districtStatus).forEach(id => {
        if (state.districtStatus[id] === 'neighbor') {
            state.districtStatus[id] = 'unassigned';
            layerMap[parseInt(id)] && layerMap[parseInt(id)].setStyle(getStyle(parseInt(id)));
        }
    });

    if (state.current.length === 0) return;

    const currentSet = new Set(state.current.map(String));
    const neighborSet = new Set();

    state.current.forEach(id => {
        (ADJACENCY_MAP[String(id)] || []).forEach(n => {
            if (!currentSet.has(n) && state.districtStatus[parseInt(n)] === 'unassigned') {
                neighborSet.add(parseInt(n));
            }
        });
    });

    neighborSet.forEach(id => {
        state.districtStatus[id] = 'neighbor';
        layerMap[id] && layerMap[id].setStyle(getStyle(id));
    });
}

function updateCurrentStats() {
    const count = state.current.length;
    document.getElementById('stat-count').textContent = count;

    if (count === 0) {
        document.getElementById('stat-dem').textContent = '—';
        document.getElementById('stat-rep').textContent = '—';
        document.getElementById('stat-leading').textContent = '—';
        document.getElementById('stat-leading').className = '';
        return;
    }

    let dem = 0, rep = 0;
    state.current.forEach(id => {
        const counts = (VOTER_COUNTS[String(id)] || {}).counts || {};
        dem += counts['DEM'] || 0;
        rep += counts['REP'] || 0;
    });

    document.getElementById('stat-dem').textContent = dem.toLocaleString();
    document.getElementById('stat-rep').textContent = rep.toLocaleString();

    const leading = dem > rep ? 'DEM' : dem < rep ? 'REP' : 'TIED';
    const el = document.getElementById('stat-leading');
    el.textContent = leading;
    el.className = leading === 'DEM' ? 'text-primary' : leading === 'REP' ? 'text-danger' : 'text-muted';
}

function updateFinalizeButton() {
    const hasSelection = state.current.length > 0;
    document.getElementById('btn-finalize').disabled = !hasSelection;
}

async function finalizeDistrict() {
    if (state.current.length === 0) return;

    setMessage('Validating...', 'alert-info');

    try {
        const res = await fetch('/game/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ district_ids: state.current, adjacency_map: ADJACENCY_MAP })
        });
        const data = await res.json();
        if (!data.valid) { setMessage(data.message, 'alert-danger'); return; }
    } catch {
        if (!isContiguousClient(state.current)) {
            setMessage('Districts are not contiguous.', 'alert-danger');
            return;
        }
    }

    let totals = {};
    state.current.forEach(id => {
        const counts = (VOTER_COUNTS[String(id)] || {}).counts || {};
        Object.entries(counts).forEach(([p, c]) => { totals[p] = (totals[p] || 0) + c; });
    });

    const winner = Object.keys(totals).length
        ? Object.keys(totals).reduce((a, b) => totals[a] > totals[b] ? a : b)
        : 'OTH';

    const adId = state.finalized.length + 1;

    state.finalized.push({ id: adId, electionDistricts: [...state.current], winner });

    state.current.forEach(id => {
        state.districtStatus[id] = 'finalized';
        state.electionToAssemblyWinner[id] = winner;
        layerMap[id] && layerMap[id].setStyle(getStyle(id));
    });

    state.totalAssigned += state.current.length;
    state.current = [];

    updateNeighbors();
    updateCurrentStats();
    updateProgress();
    updateDistrictList();
    updateFinalizeButton();
    updateCurrentDistrictNum();

    setMessage(`District ${adId} finalized — won by ${winner}.`, winner === playerParty ? 'alert-success' : 'alert-danger');

    if (state.finalized.length === MAX_ASSEMBLY) {
        setTimeout(showFinalScore, 600);
    }
}

function clearCurrent() {
    state.current.forEach(id => {
        state.districtStatus[id] = 'unassigned';
        layerMap[id] && layerMap[id].setStyle(getStyle(id));
    });
    state.current = [];
    updateNeighbors();
    updateCurrentStats();
    updateFinalizeButton();
    setMessage('Selection cleared.', 'alert-info');
}

async function showFinalScore() {
    try {
        const res = await fetch('/game/score', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                player_party: playerParty,
                assembly_districts: state.finalized.map(d => ({
                    id: d.id,
                    election_districts: d.electionDistricts
                })),
                voter_counts: VOTER_COUNTS
            })
        });
        const data = await res.json();
        renderScore(data.player_seats, data.total_seats, data.won,
            data.results.filter(r => r.winner === 'DEM').length,
            data.results.filter(r => r.winner === 'REP').length);
    } catch {
        const playerSeats = state.finalized.filter(d => d.winner === playerParty).length;
        renderScore(playerSeats, MAX_ASSEMBLY, playerSeats > MAX_ASSEMBLY / 2,
            state.finalized.filter(d => d.winner === 'DEM').length,
            state.finalized.filter(d => d.winner === 'REP').length);
    }
}

function renderScore(playerSeats, total, won, dem, rep) {
    document.getElementById('score-title').textContent = won ? 'YOU WIN!' : 'YOU LOSE';
    document.getElementById('score-title').className = `modal-title font-weight-bold text-${won ? 'success' : 'danger'}`;
    document.getElementById('score-player').textContent = playerSeats;
    document.getElementById('score-player').className = `text-${won ? 'success' : 'danger'}`;
    document.getElementById('score-total').textContent = total;
    document.getElementById('score-dem').textContent = dem;
    document.getElementById('score-rep').textContent = rep;
    $('#scoreModal').modal('show');
}

async function saveMap() {
    const nameInput = document.getElementById('save-name-input');
    const feedback = document.getElementById('save-feedback');
    const saveBtn = document.getElementById('btn-save-map');
    const name = nameInput.value.trim();
    
    if (!name) {
        feedback.textContent = 'Enter a name first.';
        feedback.className = 'mt-2 small text-danger';
        return;
    }

    if (state.finalized.length !== MAX_ASSEMBLY) {
        feedback.textContent = 'Finish the game before saving.';
        feedback.className = 'mt-2 small text-danger';
        return;
    }

    feedback.textContent = 'Saving...';
    feedback.className = 'mt-2 small text-muted';

    try {
        const res = await fetch('/game/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                map_name: name,
                player_party: playerParty,
                assembly_districts: state.finalized.map(d => ({
                    id: d.id,
                    electionDistricts: d.electionDistricts,
                    winner: d.winner
                }))
            })
        });
        const data = await res.json();

        if (data.success) {
            feedback.textContent = `Saved as "${name}"!`;
            feedback.className = 'mt-2 small text-success';
            nameInput.value = '';
            nameInput.disabled = true;
            saveBtn.disabled = true;
        } else {
            feedback.textContent = data.message || 'Save failed.';
            feedback.className = 'mt-2 small text-danger';
        }
    } catch {
        feedback.textContent = 'Network error — could not save.';
        feedback.className = 'mt-2 small text-danger';
    }
}

function updateProgress() {
    const drawn = state.finalized.length;
    document.getElementById('progress-label').textContent = `${drawn} / ${MAX_ASSEMBLY}`;
    document.getElementById('progress-fill').style.width = `${(drawn / MAX_ASSEMBLY) * 100}%`;
    document.getElementById('header-drawn').textContent = drawn;
    document.getElementById('header-assigned').textContent = state.totalAssigned;
}

function updateCurrentDistrictNum() {
    const next = state.finalized.length + 1;
    document.getElementById('current-district-num').textContent = next <= MAX_ASSEMBLY ? `#${next}` : '';
}

function updateDistrictList() {
    const list = document.getElementById('district-list');
    list.innerHTML = '';
    state.finalized.forEach(d => {
        const btn = document.createElement('button');
        btn.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center py-2 px-3 small';

        const left = document.createElement('div');
        left.className = 'd-flex align-items-center';

        const dot = document.createElement('span');
        dot.className = 'legend-swatch mr-2 mb-0';
        dot.style.backgroundColor = PARTY_COLORS[d.winner] || '#6c757d';

        const label = document.createElement('span');
        label.textContent = `Dist ${d.id} (${d.electionDistricts.length})`;

        left.appendChild(dot);
        left.appendChild(label);

        const badge = document.createElement('span');
        badge.className = `badge badge-${d.winner === 'DEM' ? 'primary' : d.winner === 'REP' ? 'danger' : 'secondary'}`;
        badge.textContent = d.winner;

        btn.appendChild(left);
        btn.appendChild(badge);

        btn.onclick = () => {
            const first = layerMap[d.electionDistricts[0]];
            if (first) map.panTo(first.getBounds().getCenter());
        };
        list.appendChild(btn);
    });
}

function setMessage(text, type) {
    const el = document.getElementById('message');
    el.textContent = text;
    el.className = `alert ${type} py-2 small`;
}



document.addEventListener("DOMContentLoaded", function () {
    console.log(LOAD_MAP_ID, SAVED_MAPS)
    initMap();
    updateProgress();
    if (LOAD_MAP_ID) {
        loadSavedMap(parseInt(LOAD_MAP_ID));
    } else {
        $('#startModal').modal('show');
    }
});
