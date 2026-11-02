/**
 * Frontend logic for CargaExpress Type B Unified Gateway.
 */

async function checkHealth(dotId, endpoint) {
    const dot = document.getElementById(dotId);
    if (!dot) return;
    try {
        const response = await fetch(endpoint, { cache: 'no-store' });
        if (response.ok) {
            dot.classList.add('online');
            dot.classList.remove('offline');
            dot.title = "Connected and healthy";
        } else {
            dot.classList.add('offline');
            dot.classList.remove('online');
            dot.title = `HTTP error: ${response.status}`;
        }
    } catch (err) {
        dot.classList.add('offline');
        dot.classList.remove('online');
        dot.title = "Connection failed";
    }
}

document.addEventListener('DOMContentLoaded', () => {
    checkHealth('dot-a', '/carrier-a/health');
    checkHealth('dot-b', '/carrier-b/health');
    checkHealth('dot-c', '/carrier-c/health');
    checkHealth('dot-d', '/carrier-d/health');

    // Poll health status every 30 seconds
    setInterval(() => {
        checkHealth('dot-a', '/carrier-a/health');
        checkHealth('dot-b', '/carrier-b/health');
        checkHealth('dot-c', '/carrier-c/health');
        checkHealth('dot-d', '/carrier-d/health');
    }, 30000);
});
