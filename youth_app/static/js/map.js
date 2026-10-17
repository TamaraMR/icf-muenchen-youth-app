(() => {
  const mapElement = document.getElementById("community-map");
  const dataElement = document.getElementById("location-data");
  if (!mapElement || !dataElement || !window.L) return;

  const locations = JSON.parse(dataElement.textContent);
  const map = L.map(mapElement, { scrollWheelZoom: false }).setView([48.1372, 11.5756], 11);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map);

  const profileUrl = (filename) => filename ? `/uploads/${encodeURIComponent(filename)}` : null;
  let language = localStorage.getItem("youth-language") || "en";
  const popupLabels = [];
  locations.forEach((person) => {
    const iconMarkup = person.profile_image
      ? '<img src="' + profileUrl(person.profile_image) + '" alt="">'
      : `<span>${person.username.slice(0, 1).toUpperCase()}</span>`;
    const icon = L.divIcon({
      className: "member-marker",
      html: `<div class="member-marker-inner">${iconMarkup}</div>`,
      iconSize: [46, 46],
      iconAnchor: [23, 23],
    });
    const marker = L.marker([person.latitude, person.longitude], { icon }).addTo(map);
    const markerImage = marker.getElement()?.querySelector("img");
    markerImage?.addEventListener("error", () => {
      const initials = document.createElement("span");
      initials.textContent = person.username.slice(0, 1).toUpperCase();
      markerImage.replaceWith(initials);
    });
    const popup = document.createElement("div");
    popup.className = "map-popup";
    const name = document.createElement("strong");
    name.textContent = person.username;
    const role = document.createElement("span");
    role.className = "popup-role";
    const updateRole = () => {
      role.textContent = person.role === "Leader"
        ? (language === "de" ? "Leitung" : "Leader")
        : (language === "de" ? "Mitglied" : "Member");
    };
    updateRole();
    const area = document.createElement("span");
    area.className = "popup-area";
    area.textContent = `${person.area}, ${person.postal_code}`;
    if (person.profile_image) {
      const photo = document.createElement("img");
      photo.className = "popup-photo";
      photo.src = profileUrl(person.profile_image);
      photo.alt = `${person.username}’s profile photo`;
      popup.append(photo);
    }
    popup.append(name, role, area);
    if (person.birthday) {
      const birthday = document.createElement("span");
      birthday.className = "popup-area";
      const updateBirthday = () => {
        birthday.textContent = `${language === "de" ? "Geburtstag" : "Birthday"} · ${person.birthday}`;
      };
      updateBirthday();
      popup.append(birthday);
      popupLabels.push({ updateRole, updateBirthday });
    } else {
      popupLabels.push({ updateRole });
    }
    if (person.bio) {
      const bio = document.createElement("p");
      bio.textContent = person.bio;
      popup.append(bio);
    }
    marker.bindPopup(popup);
  });
  window.addEventListener("youth-language-change", (event) => {
    language = event.detail;
    popupLabels.forEach((labels) => {
      labels.updateRole();
      labels.updateBirthday?.();
    });
  });

  const latitude = document.getElementById("latitude");
  const longitude = document.getElementById("longitude");
  const pinIcon = L.divIcon({
    className: "location-pin-marker",
    html: "<span></span>",
    iconSize: [28, 40],
    iconAnchor: [14, 38],
  });
  let pin = null;
  if (latitude.value && longitude.value) {
    pin = L.marker([Number(latitude.value), Number(longitude.value)], {
      icon: pinIcon,
      interactive: false,
    }).addTo(map);
  }
  const form = document.getElementById("neighborhood-form");
  const submit = form.querySelector('button[type="submit"]');
  const errorMessage = document.createElement("p");
  errorMessage.className = "geocode-error";
  errorMessage.setAttribute("role", "alert");
  form.insertBefore(errorMessage, submit);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorMessage.textContent = "";
    submit.disabled = true;
    submit.dataset.label = submit.textContent;
    submit.textContent = language === "de" ? "Standort wird gesucht …" : "Finding your area …";
    try {
      const postcode = form.elements.postal_code.value.trim();
      const area = form.elements.area.value.trim();
      const query = new URLSearchParams({
        format: "jsonv2",
        limit: "1",
        addressdetails: "1",
        countrycodes: "de",
        q: `${area}, ${postcode}, München, Deutschland`,
      });
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?${query.toString()}`,
        { headers: { Accept: "application/json" } },
      );
      if (!response.ok) throw new Error("geocoder");
      const results = await response.json();
      const result = results[0];
      const point = result && { lat: Number(result.lat), lng: Number(result.lon) };
      const resultPostcode = result?.address?.postcode?.replace(/\s/g, "");
      if (!point || !Number.isFinite(point.lat) || !Number.isFinite(point.lng)
          || point.lat < 47 || point.lat > 49 || point.lng < 10 || point.lng > 14
          || (resultPostcode && !resultPostcode.startsWith(postcode))) {
        throw new Error("not-found");
      }
      latitude.value = point.lat.toFixed(6);
      longitude.value = point.lng.toFixed(6);
      if (!pin) {
        pin = L.marker(point, { icon: pinIcon, interactive: false }).addTo(map);
      } else {
        pin.setLatLng(point);
      }
      map.flyTo(point, 13, { duration: 0.6 });
      form.submit();
    } catch (error) {
      errorMessage.textContent = error.message === "geocoder"
        ? (language === "de"
          ? "Die Kartensuche ist gerade nicht erreichbar. Bitte versuche es erneut."
          : "The map search is unavailable right now. Please try again.")
        : (language === "de"
          ? "Postleitzahl und Stadtteil wurden nicht gefunden. Bitte überprüfe deine Angaben."
          : "We couldn’t find that postcode and area. Please check the details.");
      submit.disabled = false;
      submit.textContent = submit.dataset.label;
    }
  });

  document.querySelectorAll("[data-focus-lat]").forEach((link) => {
    link.addEventListener("click", () => {
      const point = [Number(link.dataset.focusLat), Number(link.dataset.focusLon)];
      map.flyTo(point, 14, { duration: 0.6 });
      const found = locations.find((person) =>
        Number(person.latitude) === point[0] && Number(person.longitude) === point[1]);
      if (found) {
        map.eachLayer((layer) => {
          if (layer instanceof L.Marker && layer.getLatLng().lat === point[0]
              && layer.getLatLng().lng === point[1]) layer.openPopup();
        });
      }
    });
  });
})();
