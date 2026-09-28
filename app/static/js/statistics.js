document.querySelector("#statistics-queue")?.addEventListener("change", event => event.currentTarget.form.submit());
document.querySelectorAll("[data-period]").forEach(button => button.addEventListener("click", () => {
  document.querySelector("#statistics-period").value = button.dataset.period;
  button.closest("form").submit();
}));

const chart = document.querySelector("#attendance-chart");
if (chart) {
  const labels = JSON.parse(chart.dataset.labels);
  const points = JSON.parse(chart.dataset.points);
  const svg = chart.querySelector("svg");
  const width = 800, height = 250, padding = 24;
  const maximum = Math.max(...points, 1);
  const x = index => padding + index * ((width - padding * 2) / Math.max(points.length - 1, 1));
  const y = value => height - padding - (value / maximum) * (height - padding * 2);
  chart.querySelector("polyline").setAttribute("points", points.map((value,index) => `${x(index)},${y(value)}`).join(" "));
  const dots = chart.querySelector(".chart-dots");
  points.forEach((value,index) => dots.insertAdjacentHTML("beforeend", `<circle cx="${x(index)}" cy="${y(value)}" r="5"><title>${labels[index]}: ${value}</title></circle>`));
  const grid = chart.querySelector(".chart-grid");
  [0,.25,.5,.75,1].forEach(fraction => grid.insertAdjacentHTML("beforeend", `<line x1="${padding}" x2="${width-padding}" y1="${padding+(height-padding*2)*fraction}" y2="${padding+(height-padding*2)*fraction}"/>`));
  chart.querySelector(".chart-labels").innerHTML = labels.map((label,index) => `<span class="${labels.length > 15 && index % 5 !== 0 && index !== labels.length - 1 ? "muted-label" : ""}">${label}</span>`).join("");
  svg.hidden = false;
}
