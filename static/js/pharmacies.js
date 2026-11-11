

        let map; // Map variable ko globally define kiya gaya
        let currentMarkers = [];
        
        function initMap() {
            const center = { lat: 31.5204, lng: 74.3487 }; // Default center for Lahore
            map = new google.maps.Map(document.getElementById('map-container'), {
                center: center,
                zoom: 12,
            });
        }

        function addMarkers(locations) {
            // Existing markers ko clear karen
            currentMarkers.forEach(marker => marker.setMap(null));
            currentMarkers = [];

            if (locations.length > 0) {
                const bounds = new google.maps.LatLngBounds();
                locations.forEach(location => {
                    const marker = new google.maps.Marker({
                        position: { lat: location.lat, lng: location.lng },
                        map: map,
                        title: location.name,
                    });
                    currentMarkers.push(marker);
                    bounds.extend(marker.getPosition());
                });
                map.fitBounds(bounds);
            } else {
                // Fallback to center if no locations found
                const defaultCenter = { lat: 31.5204, lng: 74.3487 };
                map.setCenter(defaultCenter);
                map.setZoom(12);
            }
        }
        
        document.addEventListener('DOMContentLoaded', () => {
            const searchInput = document.getElementById('searchInput');
            const searchButton = document.getElementById('searchButton');
            const resultsHeading = document.getElementById('resultsHeading');
            const pharmacyList = document.getElementById('pharmacyList');
            const pharmacies = pharmacyList.querySelectorAll('.bg-white');

            const mapModal = document.getElementById('mapModal');
            const closeMapModal = document.getElementById('closeMapModal');
            const mapViewButton = document.getElementById('mapViewButton');
            
            searchButton.addEventListener('click', performSearch);
            searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    performSearch();
                }
            });

            mapViewButton.addEventListener('click', () => {
                mapModal.style.display = 'flex';
                // Delay map initialization to ensure modal is visible and has dimensions
                setTimeout(() => {
                    const visiblePharmacies = Array.from(pharmacies).filter(p => p.style.display !== 'none');
                    const locations = visiblePharmacies.map(p => ({
                        lat: parseFloat(p.dataset.lat),
                        lng: parseFloat(p.dataset.lng),
                        name: p.querySelector('h3').textContent
                    }));
                    addMarkers(locations);
                }, 100);
            });

            closeMapModal.addEventListener('click', () => {
                mapModal.style.display = 'none';
            });
            
            window.onclick = function(event) {
                if (event.target == mapModal) {
                    mapModal.style.display = 'none';
                }
            }

            function performSearch() {
                const query = searchInput.value.toLowerCase().trim();
                let foundCount = 0;

                if (query === '') {
                    resultsHeading.textContent = 'Popular Pharmacies';
                    pharmacies.forEach(pharmacy => {
                        pharmacy.style.display = 'block';
                    });
                    return;
                }

                pharmacies.forEach(pharmacy => {
                    const location = pharmacy.getAttribute('data-location').toLowerCase();
                    if (location.includes(query)) {
                        pharmacy.style.display = 'block';
                        foundCount++;
                    } else {
                        pharmacy.style.display = 'none';
                    }
                });

                if (foundCount > 0) {
                    resultsHeading.textContent = `${foundCount} pharmacies found for "${searchInput.value}"`;
                } else {
                    resultsHeading.textContent = `No pharmacies found for "${searchInput.value}"`;
                }
            }
        });
