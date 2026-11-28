// The timestamp itself stays readable when JavaScript is disabled.
const checked = document.querySelector('[data-age]');
if (checked) {
  function showAge() {
    const elapsed = Date.now() - Date.parse(checked.dataset.age);
    if (elapsed > Number(checked.dataset.hours) * 3600000) {
      checked.textContent = 'This edition is older than the scheduled freshness window. Check BC Parks for newer notices before travelling.';
      checked.classList.add('stale-edition');
    }
  }
  showAge();
  setInterval(showAge, 60000);
}

function revealFacility() {
  const id = location.hash.slice(1);
  const details = id.startsWith('facility-') && document.getElementById(id);
  if (details && details.tagName === 'DETAILS') details.open = true;
}
revealFacility();
window.addEventListener('hashchange', revealFacility);
