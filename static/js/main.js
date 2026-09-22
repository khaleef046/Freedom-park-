// Freedom Park — Core JavaScript

document.addEventListener("DOMContentLoaded", () => {
  // Mobile navigation hamburger toggle
  const navToggle = document.querySelector(".nav-toggle");
  const navLinks = document.querySelector(".nav-links");

  if (navToggle && navLinks) {
    navToggle.addEventListener("click", () => {
      navLinks.classList.toggle("open");
    });
  }

  // Auto-dismiss or manual dismiss for flash alerts
  const alerts = document.querySelectorAll(".alert");
  alerts.forEach((alert) => {
    // Add close button if not present
    if (!alert.querySelector(".alert-close")) {
      const closeBtn = document.createElement("button");
      closeBtn.innerHTML = "&times;";
      closeBtn.className = "alert-close";
      closeBtn.style.cssText = "background:none;border:none;font-size:1.4rem;cursor:pointer;color:inherit;margin-left:1rem;";
      closeBtn.addEventListener("click", () => alert.remove());
      alert.appendChild(closeBtn);
    }
  });
});
