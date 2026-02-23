const CONFIG = {
    API_BASE: '',
    REFRESH_INTERVAL: 2000,
    TRAFFIC_HISTORY_SIZE: 40
};

const state = {
    isConnected: false,
    trafficHistory: []
};

const $ = (id) => document.getElementById(id);

const DOM = {
    statusBadge:      $('statusBadge'),
    statusDot:        $('statusDot'),
    statusText:       $('statusText'),
    lastUpdate:       $('lastUpdate'),

    uptimeBar:        $('uptimeBar'),
    activeBar:        $('activeBar'),
    totalTrafficBar:  $('totalTrafficBar'),
    successRateBar:   $('successRateBar'),

    serverStatusBox:  $('serverStatusBox'),
    serverIcon:       $('serverIcon'),
    serverText:       $('serverText'),
    uptimeDisplay:    $('uptimeDisplay'),
    uptimeRing:       $('uptimeRing'),

    activeConnBadge:  $('activeConnBadge'),
    totalConn:        $('totalConn'),
    successConn:      $('successConn'),
    failedConn:       $('failedConn'),
    connBarFill:      $('connBarFill'),
    connBarLabel:     $('connBarLabel'),

    sentTraffic:      $('sentTraffic'),
    receivedTraffic:  $('receivedTraffic'),
    trafficChart:     $('trafficChart'),

    routingTotal:     $('routingTotal'),
    bypassedArc:      $('bypassedArc'),
    tunneledArc:      $('tunneledArc'),
    bypassedCount:    $('bypassedCount'),
    tunneledCount:    $('tunneledCount'),

    httpCount:        $('httpCount'),
    httpBar:          $('httpBar'),
    socks5Count:      $('socks5Count'),
    socks5Bar:        $('socks5Bar'),
    ssCount:          $('ssCount'),
    ssBar:            $('ssBar'),

    samplesBadge:     $('samplesBadge'),
    lyapunovValue:    $('lyapunovValue'),
    lyapunovRing:     $('lyapunovRing'),
    entropyValue:     $('entropyValue'),
    entropyRing:      $('entropyRing'),
    correlationValue: $('correlationValue'),
    correlationRing:  $('correlationRing'),

    cacheSizeBadge:   $('cacheSizeBadge'),
    hitRateValue:     $('hitRateValue'),
    hitRateRing:      $('hitRateRing'),
    cacheHits:        $('cacheHits'),
    cacheMisses:      $('cacheMisses')
};

function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(Math.abs(bytes)) / Math.log(k));
    return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[Math.min(i, sizes.length - 1)];
}

function formatUptime(seconds) {
    if (!seconds || seconds < 0) return '---';
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
}

function formatUptimeClock(seconds) {
    if (!seconds || seconds < 0) return '---';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
}

function formatNumber(num) {
    if (num === undefined || num === null) return '---';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toLocaleString();
}

function setText(el, val) {
    if (!el) return;
    const s = String(val);
    if (el.textContent !== s) {
        el.textContent = s;
        el.classList.add('value-updated');
        setTimeout(() => el.classList.remove('value-updated'), 500);
    }
}

function setOffline(el) {
    if (!el) return;
    el.textContent = '---';
}

function setRing(el, pct, circ) {
    if (!el) return;
    const dash = Math.max(0, Math.min(1, pct / 100)) * circ;
    el.setAttribute('stroke-dasharray', `${dash} ${circ}`);
}

function setBar(el, pct) {
    if (!el) return;
    el.style.width = Math.max(0, Math.min(100, pct)) + '%';
}

function showOffline() {
    state.isConnected = false;

    if (DOM.statusDot) {
        DOM.statusDot.style.background = '#ff4560';
        DOM.statusDot.style.boxShadow = '0 0 10px #ff4560';
        DOM.statusDot.style.animationName = 'none';
    }
    if (DOM.statusText) DOM.statusText.textContent = 'Offline';

    setOffline(DOM.lastUpdate);

    [DOM.uptimeBar, DOM.activeBar, DOM.totalTrafficBar, DOM.successRateBar].forEach(setOffline);

    if (DOM.serverStatusBox) DOM.serverStatusBox.className = 'server-status stopped';
    if (DOM.serverIcon) {
        DOM.serverIcon.className = 'server-icon stopped';
        DOM.serverIcon.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
        </svg>`;
    }
    if (DOM.serverText) DOM.serverText.textContent = 'OFFLINE';
    setOffline(DOM.uptimeDisplay);
    setRing(DOM.uptimeRing, 0, 283);

    setOffline(DOM.activeConnBadge);
    [DOM.totalConn, DOM.successConn, DOM.failedConn, DOM.connBarLabel].forEach(setOffline);
    setBar(DOM.connBarFill, 0);

    [DOM.sentTraffic, DOM.receivedTraffic].forEach(setOffline);
    clearChart();

    [DOM.routingTotal, DOM.bypassedCount, DOM.tunneledCount].forEach(setOffline);
    if (DOM.bypassedArc) DOM.bypassedArc.setAttribute('stroke-dasharray', '0 377');
    if (DOM.tunneledArc) DOM.tunneledArc.setAttribute('stroke-dasharray', '0 377');

    [DOM.httpCount, DOM.socks5Count, DOM.ssCount].forEach(setOffline);
    [DOM.httpBar, DOM.socks5Bar, DOM.ssBar].forEach(el => el && setBar(el, 0));

    setOffline(DOM.samplesBadge);
    [DOM.lyapunovValue, DOM.entropyValue, DOM.correlationValue].forEach(setOffline);
    [DOM.lyapunovRing, DOM.entropyRing, DOM.correlationRing].forEach(el => setRing(el, 0, 220));

    setOffline(DOM.cacheSizeBadge);
    [DOM.hitRateValue, DOM.cacheHits, DOM.cacheMisses].forEach(setOffline);
    setRing(DOM.hitRateRing, 0, 327);
}

function clearChart() {
    const c = DOM.trafficChart;
    if (!c) return;
    const ctx = c.getContext('2d');
    const w = c.offsetWidth || 300;
    const h = c.offsetHeight || 80;
    c.width = w * (window.devicePixelRatio || 1);
    c.height = h * (window.devicePixelRatio || 1);
    ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#3d4f6a';
    ctx.font = '13px "IBM Plex Mono", monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('No Data', w / 2, h / 2);
    state.trafficHistory = [];
}

function updateStats(d) {
    const now = new Date();
    if (DOM.lastUpdate) DOM.lastUpdate.textContent = now.toLocaleTimeString('en-US', { hour12: false });

    const uptime = d.uptime || 0;
    setText(DOM.uptimeBar, formatUptimeClock(uptime));
    setText(DOM.uptimeDisplay, formatUptime(uptime));
    setRing(DOM.uptimeRing, Math.min((uptime % 86400) / 864, 100), 283);

    if (DOM.serverStatusBox) DOM.serverStatusBox.className = 'server-status';
    if (DOM.serverIcon) {
        DOM.serverIcon.className = 'server-icon running';
        DOM.serverIcon.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg>`;
    }
    if (DOM.serverText) DOM.serverText.textContent = 'RUNNING';

    const conn = d.connections || {};
    const active  = conn.active  || 0;
    const total   = conn.total   || 0;
    const success = conn.success || 0;
    const failed  = conn.failed  || 0;
    const rate    = total > 0 ? (success / total * 100) : 0;

    setText(DOM.activeBar, formatNumber(active));
    setText(DOM.successRateBar, rate.toFixed(1) + '%');
    if (DOM.activeConnBadge) DOM.activeConnBadge.textContent = `${active} active`;
    setText(DOM.totalConn, formatNumber(total));
    setText(DOM.successConn, formatNumber(success));
    setText(DOM.failedConn, formatNumber(failed));
    setBar(DOM.connBarFill, rate);
    if (DOM.connBarLabel) DOM.connBarLabel.textContent = rate.toFixed(0) + '%';

    const tr   = d.traffic || {};
    const sent = tr.sent     || 0;
    const recv = tr.received || 0;
    const tot  = tr.total    || (sent + recv);

    setText(DOM.totalTrafficBar, formatBytes(tot));
    setText(DOM.sentTraffic, formatBytes(sent));
    setText(DOM.receivedTraffic, formatBytes(recv));

    state.trafficHistory.push(tot);
    if (state.trafficHistory.length > CONFIG.TRAFFIC_HISTORY_SIZE) state.trafficHistory.shift();
    drawChart();

    const routing  = d.routing   || {};
    const bypassed = routing.bypassed || 0;
    const tunneled = routing.tunneled || 0;
    const rtTotal  = bypassed + tunneled;

    setText(DOM.routingTotal, formatNumber(rtTotal));
    setText(DOM.bypassedCount, formatNumber(bypassed));
    setText(DOM.tunneledCount, formatNumber(tunneled));
    updateDonut(bypassed, tunneled);

    const proto     = d.protocols  || {};
    const http      = proto.HTTP         || 0;
    const socks5    = proto.SOCKS5       || 0;
    const ss        = proto.Shadowsocks  || 0;
    const protoTot  = http + socks5 + ss;

    setText(DOM.httpCount,   formatNumber(http));
    setText(DOM.socks5Count, formatNumber(socks5));
    setText(DOM.ssCount,     formatNumber(ss));
    setBar(DOM.httpBar,   protoTot > 0 ? http   / protoTot * 100 : 0);
    setBar(DOM.socks5Bar, protoTot > 0 ? socks5 / protoTot * 100 : 0);
    setBar(DOM.ssBar,     protoTot > 0 ? ss     / protoTot * 100 : 0);
}

function updateChaos(d) {
    const ly  = parseFloat(d.lyapunov_exponent)    || 0;
    const en  = parseFloat(d.shannon_entropy)       || 0;
    const co  = parseFloat(d.correlation_dimension) || 0;
    const sam = d.samples_collected || 0;

    setText(DOM.lyapunovValue,    ly.toFixed(3));
    setText(DOM.entropyValue,     en.toFixed(2));
    setText(DOM.correlationValue, co.toFixed(3));
    if (DOM.samplesBadge) DOM.samplesBadge.textContent = formatNumber(sam) + ' samples';

    setRing(DOM.lyapunovRing,    Math.min(Math.abs(ly) * 100, 100), 220);
    setRing(DOM.entropyRing,     Math.min(en / 8 * 100, 100),       220);
    setRing(DOM.correlationRing, Math.min(Math.abs(co) / 3 * 100, 100), 220);
}

function updateDNS(d) {
    const size   = d.cache_size   || 0;
    const hits   = d.cache_hits   || 0;
    const misses = d.cache_misses || 0;

    let hitRate = 0;
    if (d.hit_rate) {
        hitRate = parseFloat(String(d.hit_rate).replace('%', '')) || 0;
    } else if (hits + misses > 0) {
        hitRate = hits / (hits + misses) * 100;
    }

    if (DOM.cacheSizeBadge) DOM.cacheSizeBadge.textContent = formatNumber(size) + ' entries';
    setText(DOM.hitRateValue, hitRate.toFixed(1) + '%');
    setText(DOM.cacheHits,    formatNumber(hits));
    setText(DOM.cacheMisses,  formatNumber(misses));
    setRing(DOM.hitRateRing, hitRate, 327);
}

function updateDonut(bypassed, tunneled) {
    const total = bypassed + tunneled;
    const CIRC  = 377; 

    if (total === 0) {
        if (DOM.bypassedArc) DOM.bypassedArc.setAttribute('stroke-dasharray', `0 ${CIRC}`);
        if (DOM.tunneledArc) DOM.tunneledArc.setAttribute('stroke-dasharray', `0 ${CIRC}`);
        return;
    }

    const bDash = (bypassed / total) * CIRC;
    const tDash = (tunneled / total) * CIRC;

    if (DOM.bypassedArc) {
        DOM.bypassedArc.setAttribute('stroke-dasharray',  `${bDash} ${CIRC}`);
        DOM.bypassedArc.setAttribute('stroke-dashoffset', '0');
    }
    if (DOM.tunneledArc) {
        DOM.tunneledArc.setAttribute('stroke-dasharray',  `${tDash} ${CIRC}`);
        DOM.tunneledArc.setAttribute('stroke-dashoffset', `-${bDash}`);
    }
}

function drawChart() {
    const canvas = DOM.trafficChart;
    if (!canvas) return;

    const ctx  = canvas.getContext('2d');
    const dpr  = window.devicePixelRatio || 1;
    const W    = canvas.offsetWidth  || 300;
    const H    = canvas.offsetHeight || 80;

    canvas.width  = W * dpr;
    canvas.height = H * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, H);

    const data = state.trafficHistory;
    if (data.length < 2) {
        ctx.fillStyle = '#3d4f6a';
        ctx.font = '13px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('Collecting data...', W / 2, H / 2);
        return;
    }

    const pad   = { t: 6, r: 10, b: 6, l: 10 };
    const gW    = W - pad.l - pad.r;
    const gH    = H - pad.t - pad.b;
    const max   = Math.max(...data);
    const min   = Math.min(...data);
    const range = max - min || 1;

    const pts = data.map((v, i) => ({
        x: pad.l + (i / (data.length - 1)) * gW,
        y: pad.t + (1 - (v - min) / range) * gH
    }));

    const grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, 'rgba(0,212,255,0.35)');
    grad.addColorStop(1, 'rgba(0,212,255,0)');

    ctx.beginPath();
    ctx.moveTo(pts[0].x, H - pad.b);
    pts.forEach(p => ctx.lineTo(p.x, p.y));
    ctx.lineTo(pts[pts.length - 1].x, H - pad.b);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    ctx.beginPath();
    pts.forEach((p, i) => i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y));
    ctx.strokeStyle = '#00d4ff';
    ctx.lineWidth   = 2;
    ctx.lineCap     = 'round';
    ctx.lineJoin    = 'round';
    ctx.shadowColor = '#00d4ff';
    ctx.shadowBlur  = 8;
    ctx.stroke();
    ctx.shadowBlur  = 0;

    const lp = pts[pts.length - 1];
    ctx.beginPath();
    ctx.arc(lp.x, lp.y, 4, 0, Math.PI * 2);
    ctx.fillStyle = '#00d4ff';
    ctx.shadowColor = '#00d4ff';
    ctx.shadowBlur  = 12;
    ctx.fill();
    ctx.shadowBlur  = 0;
}

async function api(path) {
    const r = await fetch(CONFIG.API_BASE + path);
    if (!r.ok) throw new Error(r.status);
    return r.json();
}

async function tick() {
    try {
        const [stats, chaos, dns] = await Promise.all([
            api('/api/stats'),
            api('/api/chaos'),
            api('/api/dns')
        ]);

        if (!state.isConnected) {
            state.isConnected = true;
            if (DOM.statusDot) {
                DOM.statusDot.style.background   = '#00e5a0';
                DOM.statusDot.style.boxShadow    = '0 0 10px rgba(0,229,160,.6)';
                DOM.statusDot.style.animationName = 'pulse';
            }
            if (DOM.statusText) DOM.statusText.textContent = 'Connected';
        }

        updateStats(stats);
        updateChaos(chaos);
        updateDNS(dns);

    } catch (err) {
        console.warn('API unreachable:', err.message);
        showOffline();
    }
}

function init() {
    console.log('Chaos Traffic Engine Dashboard');
    showOffline();
    tick();
    setInterval(tick, CONFIG.REFRESH_INTERVAL);

    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(drawChart, 100);
    });
}

document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', init)
    : init();