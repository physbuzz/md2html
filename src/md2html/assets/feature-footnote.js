(function () {
  function setup() {
    var references = document.querySelectorAll('a.footnote-ref');
    if (!references.length || document.querySelector('.footnote-tooltip')) return;
    var tooltip = document.createElement('a');
    tooltip.className = 'footnote-tooltip';
    tooltip.id = 'md2html-footnote-tooltip';
    tooltip.hidden = true;
    document.body.appendChild(tooltip);
    var active = null;
    var timer;

    function hide() {
      clearTimeout(timer);
      tooltip.hidden = true;
      if (active) active.removeAttribute('aria-describedby');
      active = null;
    }

    function scheduleHide() {
      clearTimeout(timer);
      timer = setTimeout(function () {
        if (!tooltip.matches(':hover, :focus') && !(active && active.matches(':hover, :focus'))) hide();
      }, 150);
    }

    function position() {
      if (!active) return;
      var ref = active.getBoundingClientRect();
      var box = tooltip.getBoundingClientRect();
      var left = Math.max(8, Math.min(ref.left, innerWidth - box.width - 8));
      var top = ref.bottom + 4;
      if (top + box.height > innerHeight - 8) top = ref.top - box.height - 4;
      tooltip.style.left = left + 'px';
      tooltip.style.top = Math.max(8, top) + 'px';
    }

    references.forEach(function (ref) {
      var target = document.getElementById(ref.getAttribute('href').slice(1));
      if (!target) return;
      function show() {
        hide();
        active = ref;
        var copy = target.cloneNode(true);
        copy.querySelectorAll('.footnote-backref, script, style').forEach(function (node) { node.remove(); });
        // Keep paragraph boundaries in the plain-text preview without copying interactive markup or IDs.
        copy.querySelectorAll('p, li, pre, br').forEach(function (node) { node.appendChild(document.createTextNode('\n')); });
        tooltip.textContent = copy.textContent.trim();
        tooltip.href = ref.getAttribute('href');
        ref.setAttribute('aria-describedby', tooltip.id);
        tooltip.hidden = false;
        position();
      }
      ref.addEventListener('mouseenter', show);
      ref.addEventListener('focus', show);
      ref.addEventListener('mouseleave', scheduleHide);
      ref.addEventListener('blur', scheduleHide);
      ref.addEventListener('click', hide);
    });
    tooltip.addEventListener('mouseenter', function () { clearTimeout(timer); });
    tooltip.addEventListener('mouseleave', scheduleHide);
    tooltip.addEventListener('blur', scheduleHide);
    tooltip.addEventListener('click', hide);
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && active) {
        var ref = active;
        if (document.activeElement === tooltip) ref.focus();
        hide();
      }
    });
    window.addEventListener('resize', position);
    document.addEventListener('scroll', position, true);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', setup);
  else setup();
})();
