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
  locations.forEach((person) => {
    const iconMarkup = person.profile_image
      ? `<img src="${profileUrl(person.profile_image)}" alt="">`
      : `<span>${person.username.slice(0, 1).toUpperCase()}</span>`;
    const icon = L.divIcon({
      className: "member-marker",
      html: `<div class="member-marker-inner">${iconMarkup}</div>`,
      iconSize: [46, 46],
      iconAnchor: [23, 23],
    });
    const marker = L.marker([person.latitude, person.longitude], { icon }).addTo(map);
    const popup = document.createElement("div");
    popup.className = "map-popup";
    const name = document.createElement("strong");
    name.textContent = person.username;
    const role = document.createElement("span");
    role.className = "popup-role";
    role.textContent = person.role;
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
      birthday.textContent = `Birthday · ${person.birthday}`;
      popup.append(birthday);
    }
    if (person.bio) {
      const bio = document.createElement("p");
      bio.textContent = person.bio;
      popup.append(bio);
    }
    marker.bindPopup(popup);
  });

  const latitude = document.getElementById("latitude");
  const longitude = document.getElementById("longitude");
  const pin = L.marker(
    latitude.value && longitude.value ? [Number(latitude.value), Number(longitude.value)] : map.getCenter(),
    {
      draggable: true,
      opacity: latitude.value && longitude.value ? 1 : 0.55,
      icon: L.divIcon({
        className: "location-pin-marker",
        html: "<span></span>",
        iconSize: [28, 40],
        iconAnchor: [14, 38],
      }),
    },
  ).addTo(map);
  const savePosition = (point) => {
    latitude.value = point.lat.toFixed(6);
    longitude.value = point.lng.toFixed(6);
    pin.setOpacity(1);
  };
  pin.on("dragend", () => savePosition(pin.getLatLng()));
  map.on("click", (event) => {
    pin.setLatLng(event.latlng);
    savePosition(event.latlng);
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
              && layer.getLatLng().lng === point[1] && layer !== pin) layer.openPopup();
        });
      }
    });
  });
})();
