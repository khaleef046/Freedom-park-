// Freedom Park — Interactive Calendar Component

class FreedomCalendar {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    if (!this.container) return;

    const today = new Date();
    this.currentYear = options.initialYear || today.getFullYear();
    this.currentMonth = options.initialMonth || today.getMonth() + 1;
    this.onDateSelected = options.onDateSelected || null;
    this.selectedDate = options.selectedDate || null;
    this.isAdmin = options.isAdmin || false;

    this.monthNames = [
      "January", "February", "March", "April", "May", "June",
      "July", "August", "September", "October", "November", "December"
    ];

    this.init();
  }

  async init() {
    await this.loadMonthData(this.currentYear, this.currentMonth);
  }

  async loadMonthData(year, month) {
    this.container.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--color-text-muted);">Loading calendar availability...</div>';

    try {
      const resp = await fetch(`/api/calendar?year=${year}&month=${month}`);
      const data = await resp.json();
      this.render(data);
    } catch (err) {
      this.container.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--color-danger);">Failed to load calendar. Please refresh.</div>';
    }
  }

  render(data) {
    const monthTitle = `${this.monthNames[this.currentMonth - 1]} ${this.currentYear}`;

    let html = `
      <div class="calendar-nav">
        <button type="button" class="btn btn-secondary btn-sm cal-prev-btn">&larr; Previous</button>
        <span class="calendar-nav-title">${monthTitle}</span>
        <button type="button" class="btn btn-secondary btn-sm cal-next-btn">Next &rarr;</button>
      </div>

      <div class="calendar-legend">
        <div class="legend-item"><span class="legend-color legend-available"></span> Available</div>
        <div class="legend-item"><span class="legend-color legend-booked"></span> Booked / Blocked</div>
        <div class="legend-item"><span class="legend-color legend-past"></span> Past</div>
      </div>

      <div class="calendar-grid-header">
        <div>Sun</div><div>Mon</div><div>Tue</div><div>Wed</div><div>Thu</div><div>Fri</div><div>Sat</div>
      </div>

      <div class="calendar-grid-days">
    `;

    // Compute first day of week padding
    const firstDayIndex = new Date(this.currentYear, this.currentMonth - 1, 1).getDay();
    for (let i = 0; i < firstDayIndex; i++) {
      html += '<div class="cal-day cal-past" style="background:transparent;border:none;cursor:default;"></div>';
    }

    data.days.forEach((day) => {
      let stateClass = "cal-available";
      let statusLabel = `₹${day.price}`;

      if (day.status === "PAST") {
        stateClass = "cal-past";
        statusLabel = "Past";
      } else if (day.status === "BOOKED") {
        stateClass = "cal-booked";
        statusLabel = "Booked";
      } else if (day.status === "BLOCKED") {
        stateClass = "cal-blocked";
        statusLabel = "Blocked";
      }

      const isSelected = this.selectedDate === day.date;
      if (isSelected) stateClass += " cal-selected";

      html += `
        <div class="cal-day ${stateClass}" data-date="${day.date}" data-status="${day.status}" data-price="${day.price}">
          <span class="cal-day-num">${day.day}</span>
          <span class="cal-day-price">${statusLabel}</span>
        </div>
      `;
    });

    html += "</div>";
    this.container.innerHTML = html;

    // Attach navigation event handlers
    this.container.querySelector(".cal-prev-btn").addEventListener("click", () => {
      this.currentMonth--;
      if (this.currentMonth < 1) {
        this.currentMonth = 12;
        this.currentYear--;
      }
      this.loadMonthData(this.currentYear, this.currentMonth);
    });

    this.container.querySelector(".cal-next-btn").addEventListener("click", () => {
      this.currentMonth++;
      if (this.currentMonth > 12) {
        this.currentMonth = 1;
        this.currentYear++;
      }
      this.loadMonthData(this.currentYear, this.currentMonth);
    });

    // Attach day selection handlers
    this.container.querySelectorAll(".cal-day").forEach((el) => {
      el.addEventListener("click", () => {
        const dateVal = el.dataset.date;
        const status = el.dataset.status;
        const price = el.dataset.price;

        if (!dateVal) return;

        if (status === "AVAILABLE" || this.isAdmin) {
          // Remove previous selection highlight
          this.container.querySelectorAll(".cal-day").forEach((d) => d.classList.remove("cal-selected"));
          el.classList.add("cal-selected");
          this.selectedDate = dateVal;

          if (typeof this.onDateSelected === "function") {
            this.onDateSelected(dateVal, status, price);
          }
        }
      });
    });
  }
}

window.FreedomCalendar = FreedomCalendar;
