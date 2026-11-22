// Scroll behaviour. Normal scrolling throughout: nothing here intercepts or changes
// the scroll, it only reacts to it. At most two depth layers per screen (the ghost
// card on the first screen, the faint chapter number behind each chapter opening).

export const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

// Calls onStep(n) when a different step crosses the trigger line. A plain scroll
// listener rather than IntersectionObserver: it is deterministic, cheap for a dozen
// boxes, and keeps working where observers are throttled.
const isPhone = () => matchMedia("(max-width: 820px)").matches;

export function observeSteps(scrolly, onStep) {
  const steps = [...scrolly.querySelectorAll(".stp")];
  let current = 0;
  const check = () => {
    // On a phone the graphic pins to the top half, so the line sits lower, where the
    // step text is visible below the graphic.
    const line = innerHeight * (isPhone() ? 0.78 : 0.55);
    let n = 1;
    for (const st of steps) if (st.getBoundingClientRect().top <= line) n = Number(st.dataset.step);
    if (n === current) return;
    current = n;
    steps.forEach((st) => st.classList.toggle("on", Number(st.dataset.step) === n));
    onStep(n);
  };
  addEventListener("scroll", check, { passive: true });
  addEventListener("resize", check);
  check();
}

export function parallax() {
  if (reducedMotion()) return;
  const ghost = document.querySelector(".ghost");
  const nums = [...document.querySelectorAll(".chead .num")];
  let queued = false;
  const frame = () => {
    queued = false;
    const y = scrollY, vh = innerHeight;
    if (ghost && y < vh * 1.2) ghost.style.transform = `translate3d(0, ${y * -0.22}px, 0)`;
    for (const n of nums) {
      const top = n.parentElement.getBoundingClientRect().top;
      if (top < vh * 1.3 && top > -vh) n.style.transform = `translate3d(0, ${(top - vh / 2) * 0.18}px, 0)`;
    }
  };
  addEventListener("scroll", () => { if (!queued) { queued = true; requestAnimationFrame(frame); } }, { passive: true });
  frame();
}
