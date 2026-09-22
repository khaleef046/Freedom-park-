// Freedom Park — Premium Brand Intro Animation

document.addEventListener("DOMContentLoaded", () => {
  const splash = document.getElementById("splashIntro");
  if (!splash) return;

  // If splash was already viewed during this browser session, hide immediately
  if (sessionStorage.getItem("fp_splash_viewed")) {
    splash.style.display = "none";
    return;
  }

  const dismissSplash = () => {
    splash.classList.add("fade-out");
    sessionStorage.setItem("fp_splash_viewed", "true");
    setTimeout(() => {
      splash.style.display = "none";
    }, 600);
  };

  // Auto-dismiss after 2.4 seconds
  const timer = setTimeout(dismissSplash, 2400);

  // Allow instant skip via button or screen tap
  const skipBtn = document.getElementById("splashSkipBtn");
  if (skipBtn) {
    skipBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      clearTimeout(timer);
      dismissSplash();
    });
  }

  splash.addEventListener("click", () => {
    clearTimeout(timer);
    dismissSplash();
  });
});
