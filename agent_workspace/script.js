/* ============================================
   WINTER/SCENT — script.js
   Scroll-reveal animations + light parallax on the
   hero type. No interactive controls by design.
   ============================================ */

(function () {
  "use strict";

  /* ---------- Scroll reveal ---------- */
  const revealTargets = [
    "section.hero > *",
    ".rules-card",
    ".pick",
    ".picks-head",
    ".wear-card"
  ];

  document.querySelectorAll(revealTargets.join(",")).forEach((el) => {
    el.classList.add("reveal");
  });

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );

  document.querySelectorAll(".reveal").forEach((el, i) => {
    // Small stagger so cards cascade in
    el.style.transitionDelay = (i % 4) * 90 + "ms";
    observer.observe(el);
  });

  /* ---------- Hero title drift ----------
     The three big lines shift a few pixels at different
     rates on scroll — cheap, poster-like depth. */
  const heroLines = Array.from(
    document.querySelectorAll(".hero-line")
  );

  const speeds = [0.04, 0.09, 0.14];
  let ticking = false;

  function drift() {
    const y = window.scrollY;
    heroLines.forEach((line, i) => {
      line.style.transform = "translateY(" + (y * speeds[i]) + "px)";
    });
    ticking = false;
  }

  window.addEventListener(
    "scroll",
    () => {
      if (!ticking) {
        window.requestAnimationFrame(drift);
        ticking = true;
      }
    },
    { passive: true }
  );

  /* Respect reduced-motion preferences */
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    document.querySelectorAll(".reveal").forEach((el) => {
      el.classList.add("is-visible");
      el.style.transition = "none";
    });
  }
})();
