// Navbar scroll effect
const navbar = document.getElementById('navbar');
if (navbar) {
    window.addEventListener('scroll', () => {
        navbar.style.background = window.scrollY > 50
            ? 'rgba(8,8,8,.99)'
            : 'linear-gradient(to bottom, rgba(8,8,8,.98), rgba(8,8,8,.85))';
    }, { passive: true });
}

// Auto-dismiss flash messages
document.querySelectorAll('.flash').forEach(el => {
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .5s'; setTimeout(() => el.remove(), 500); }, 3500);
});

// Upcoming movie prediction
async function runPred(movieId) {
    const btn = document.querySelector(`#pred-${movieId} .pred-run-btn`);
    if (!btn) return;
    btn.textContent = '⏳ Se calculează...'; btn.disabled = true;
    try {
        const resp = await fetch(`/api/upcoming/predict/${movieId}`, { method: 'POST' });
        const data = await resp.json();
        if (data.predicted_rating) window.location.reload();
    } catch (e) {
        btn.textContent = '❌ Eroare'; btn.disabled = false;
    }
}

// Animate bars on scroll
const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => { if (e.isIntersecting) e.target.style.animationPlayState = 'running'; });
}, { threshold: 0.2 });
document.querySelectorAll('.pred-bar-fill').forEach(el => {
    el.style.animationPlayState = 'paused';
    observer.observe(el);
});
