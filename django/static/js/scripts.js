// Bind example keyword shortcut if present
(function(){
  var exampleLink = document.getElementById('example-link');
  if (!exampleLink) return;
  exampleLink.addEventListener('click', function (event) {
      event.preventDefault();  // Prevent the default link behavior
      const searchInput = document.getElementById('search-keyword');
      if (searchInput) {
        searchInput.value = 'Polyketide';  // Set the value of the input field
      }
      // Optionally, submit the form automatically
      // document.getElementById('keyword-form').submit();
  });
})();

// Global spinner helpers
function getGlobalSpinner() {
  return document.querySelector('.bgcs-portal-spinner');
}

function showGlobalSpinner() {
  var spinner = getGlobalSpinner();
  if (spinner) spinner.style.display = 'block';
}

window.addEventListener('DOMContentLoaded', () => {
  // Attach spinner behavior to all known forms
  const formIds = ['keyword-form', 'search-form', 'sequence-search-form'];
  formIds.forEach(id => {
    const form = document.getElementById(id);
    if (!form) return;
    form.addEventListener('submit', () => {
      showGlobalSpinner();
      // Only disable submit buttons to prevent double-submit; disabling all inputs strips them from the GET query string
      form.querySelectorAll('button[type="submit"]').forEach(el => (el.disabled = true));
    });
  });
});
