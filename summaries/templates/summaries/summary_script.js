// Ask for the summary after the details show, so they open fast.
window.hookSummary = function (root) {
  (root || document).querySelectorAll(".js-summary").forEach(function (form) {
    if (form.dataset.hooked) return;
    form.dataset.hooked = "1";
    function send(event) {
      if (event) event.preventDefault();
      fetch(form.action, {method: "POST", body: new FormData(form)})
        .then(function (r) { return r.ok ? r.text() : Promise.reject(r.status); })
        .then(function (html) {
          var box = form.closest("#summary-box");
          var wrap = document.createElement("div"); wrap.innerHTML = html;
          var fresh = wrap.firstElementChild;
          box.replaceWith(fresh);
          window.hookSummary(fresh.parentNode);
        })
        .catch(function () {
          var line = form.closest("#summary-box").querySelector(".loading");
          if (line) line.textContent = "Couldn't make a summary right now.";
        });
    }
    form.addEventListener("submit", send);
    if (form.classList.contains("js-auto")) send();
  });
};
window.hookSummary();
