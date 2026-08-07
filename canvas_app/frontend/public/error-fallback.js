window.__HTML_ERROR_FALLBACK = function () {
  document.getElementById('root').innerHTML =
    '<div style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:system-ui,sans-serif;flex-direction:column;gap:12px;padding:20px;text-align:center;background:#0d0d0d;color:#e0e0e0">' +
    '<h2 style="font-size:18px;margin:0">Something went wrong</h2>' +
    '<p style="font-size:14px;color:#888;margin:0">H.I.I.L. encountered an error during startup.</p>' +
    '<button id="reload-btn" style="padding:8px 20px;border-radius:6px;border:1px solid #333;background:#1a1a1a;color:#e0e0e0;cursor:pointer;font-size:14px">Reload</button>' +
    '</div>';
  document.getElementById('reload-btn').addEventListener('click', function () {
    location.reload();
  });
};
window.addEventListener('error', window.__HTML_ERROR_FALLBACK);
window.addEventListener('unhandledrejection', window.__HTML_ERROR_FALLBACK);
