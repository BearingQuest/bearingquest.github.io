(function () {
  "use strict";

  var root = document.documentElement;
  var choices = ["auto", "light", "dark"];
  var selected = "auto";

  root.classList.add("js");

  try {
    var stored = localStorage.getItem("bearing-quest-theme");
    if (choices.indexOf(stored) !== -1) {
      selected = stored;
    }
  } catch (error) {
    selected = "auto";
  }

  function applyTheme(choice) {
    if (choice === "auto") {
      root.removeAttribute("data-theme");
    } else {
      root.setAttribute("data-theme", choice);
    }
  }

  applyTheme(selected);

  document.addEventListener("DOMContentLoaded", function () {
    var controls = document.querySelectorAll('input[name="theme"]');
    var status = document.querySelector("[data-theme-status]");

    controls.forEach(function (control) {
      control.checked = control.value === selected;
      control.addEventListener("change", function () {
        if (!control.checked || choices.indexOf(control.value) === -1) {
          return;
        }

        selected = control.value;
        applyTheme(selected);

        try {
          localStorage.setItem("bearing-quest-theme", selected);
        } catch (error) {
          // The selected theme still applies for this page view.
        }

        if (status) {
          status.textContent =
            "Theme: " + selected.charAt(0).toUpperCase() + selected.slice(1);
        }
      });
    });

    if (status) {
      status.textContent =
        "Theme: " + selected.charAt(0).toUpperCase() + selected.slice(1);
    }
  });
})();
