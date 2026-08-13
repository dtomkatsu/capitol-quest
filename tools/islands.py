"""Per-island model for the Capitol Quest map engine.

Each island entry drives build_map.py (tile classification) and, through
build/map_grid_<slug>.json, render_map.py (baked pixels). Geography is
hand-modeled but REAL: ridgelines follow the actual crests, craters and
calderas sit at their true coordinates, ag fields cover the historical
plantation plains, and urban tiles come from data (road density on Oʻahu,
Census 2020 urban areas + hand town spots elsewhere — small towns like
Kaunakakai fall under the Census urban-area threshold).

Scale note: the runtime is ONE continuous world at a 0.32 km/tile
reference scale (see tools/build_world.py). Every island bakes at 0.32
except Hawaiʻi at exactly 0.64 = 2× the reference — its slices display
at integer 2× (crisp for pixel art) so the island occupies its true
footprint while the bake stays inside texture budgets. Keep any future
tile_km an integer multiple of 0.32.

Ridge tuple: (crest_pts, w_mtn_km, w_forest_km, w_peak_km, h_mult)
Crater tuple: (lon, lat, rim_inner_km, rim_outer_km, rim_height)
Town tuple: (lon, lat, radius_km)   -> urban tiles (sub-UA settlements)
Field/bay/core boxes: (lon0, lat0, lon1, lat1)
"""

# --------------------------------------------------------------- Oʻahu
# (unchanged from the original single-island engine — keep byte-stable)
KOOLAU = [(-157.990, 21.620), (-157.945, 21.575), (-157.900, 21.520),
          (-157.865, 21.470), (-157.830, 21.420), (-157.800, 21.380),
          (-157.788, 21.350), (-157.760, 21.330), (-157.715, 21.318),
          (-157.670, 21.305)]
WAIANAE = [(-158.260, 21.555), (-158.225, 21.535), (-158.200, 21.520),
           (-158.145, 21.507), (-158.120, 21.470), (-158.105, 21.430),
           (-158.090, 21.390), (-158.075, 21.360)]

ISLANDS = {
    "oahu": {
        "name": "Oʻahu",
        "grid": 288, "tile_km": 0.32,
        "center": (-157.965, 21.4825),
        "km_per_lon": 103.8, "km_per_lat": 110.9,   # pinned (legacy)
        "outline": "data/island_outline.geojson",
        "ridges": [(KOOLAU, 1.8, 3.6, 0.55, 1.0),
                   (WAIANAE, 2.3, 4.2, 0.70, 1.0)],
        "craters": [(-157.8055, 21.2620, 0.45, 1.00, 8),   # Lēʻahi
                    (-157.6773, 21.2905, 0.30, 0.70, 8),   # Koko
                    (-157.8457, 21.3066, 0.00, 0.38, 8)],  # Pūowaina
        "fields": [(-158.16, 21.42, -157.92, 21.62),
                   (-158.12, 21.33, -157.99, 21.42)],
        "core": (-157.875, 21.270, -157.815, 21.320),
        "urban": "roads",
        "towns": [],
        "bays": [(-157.855, 21.39, -157.73, 21.53)],        # render reef feather
        "bays_tiles": [(-157.84, 21.40, -157.75, 21.51)],   # build shallow rings
        "rail": True,
        "home": "capitol",
        "landmarks": [
            ("capitol", "Hawaiʻi State Capitol", -157.85736, 21.30737, "capitol"),
            ("iolani", "ʻIolani Palace", -157.85868, 21.30655, "poi"),
            ("honolulu", "Honolulu", -157.8630, 21.2930, "town"),
            ("waikiki", "Waikīkī", -157.8270, 21.2780, "town"),
            ("diamondhead", "Lēʻahi (Diamond Head)", -157.8055, 21.2600, "nature"),
            ("pearlharbor", "Pearl Harbor", -157.9600, 21.3550, "nature"),
            ("kaneohe", "Kāneʻohe", -157.8000, 21.4080, "town"),
            ("kailua", "Kailua", -157.7400, 21.3930, "town"),
            ("kapolei", "Kapolei", -158.0580, 21.3350, "town"),
            ("waianae", "Waiʻanae", -158.1850, 21.4470, "town"),
            ("wahiawa", "Wahiawā", -158.0240, 21.5030, "town"),
            ("haleiwa", "Haleʻiwa", -158.1030, 21.5930, "town"),
            ("koolau", "Koʻolau Range", -157.8650, 21.4700, "range"),
            ("waianaerange", "Waiʻanae Range", -158.1450, 21.4900, "range"),
        ],
    },

    # ------------------------------------------------------------ Kauaʻi
    "kauai": {
        "name": "Kauaʻi",
        "grid": 224, "tile_km": 0.32,
        "center": (-159.54, 22.045),
        "km_per_lon": 103.2, "km_per_lat": 110.9,
        "outline": "data/coastlines/kauai.geojson",
        "ridges": [
            # central massif: Kōkeʻe uplands to Waiʻaleʻale/Kawaikini
            ([(-159.58, 22.13), (-159.55, 22.09), (-159.50, 22.06),
              (-159.47, 22.02), (-159.49, 21.97)], 4.0, 8.5, 1.0, 1.3),
            # Nā Pali coastal ridge
            ([(-159.75, 22.09), (-159.70, 22.16), (-159.62, 22.20),
              (-159.56, 22.22)], 1.6, 3.2, 0.5, 0.9),
            # Hāʻupu ridge (SE)
            ([(-159.42, 21.92), (-159.38, 21.93)], 1.0, 2.0, 0.3, 0.5),
        ],
        "craters": [],
        "fields": [(-159.62, 21.88, -159.40, 21.94),        # Kōloa/ʻEleʻele
                   (-159.78, 21.95, -159.70, 22.02)],       # Kekaha flats
        "core": None,
        "urban": "ua",
        "towns": [(-159.502, 22.203, 0.5)],                 # Hanalei
        "bays": [],
        "bays_tiles": [],
        "rail": False,
        "home": "lihue",
        "landmarks": [
            ("lihue", "Līhuʻe", -159.371, 21.981, "town"),
            ("kapaa", "Kapaʻa", -159.338, 22.078, "town"),
            ("waimea", "Waimea", -159.669, 21.958, "town"),
            ("hanalei", "Hanalei", -159.502, 22.204, "town"),
            ("poipu", "Poʻipū", -159.469, 21.874, "town"),
            ("waialeale", "Waiʻaleʻale", -159.50, 22.06, "range"),
            ("napali", "Nā Pali Coast", -159.70, 22.17, "nature"),
            ("waimeacanyon", "Waimea Canyon", -159.66, 22.07, "nature"),
        ],
    },

    # ----------------------------------------------------------- Niʻihau
    "niihau": {
        "name": "Niʻihau",
        "grid": 128, "tile_km": 0.32,
        "center": (-160.14, 21.89),
        "km_per_lon": 103.3, "km_per_lat": 110.9,
        "outline": "data/coastlines/niihau.geojson",
        "ridges": [
            # east-side scarp (Pānīʻau)
            ([(-160.06, 21.98), (-160.10, 21.92),
              (-160.13, 21.86)], 1.3, 2.3, 0.4, 0.5),
        ],
        "craters": [],
        "fields": [],
        "core": None,
        "urban": "ua",
        "towns": [(-160.203, 21.905, 0.6)],                 # Puʻuwai
        "bays": [],
        "bays_tiles": [],
        "rail": False,
        "home": "puuwai",
        "landmarks": [
            ("puuwai", "Puʻuwai", -160.203, 21.905, "town"),
            ("paniau", "Pānīʻau", -160.10, 21.88, "range"),
        ],
    },

    # ---------------------------------------------------------- Molokaʻi
    "molokai": {
        "name": "Molokaʻi",
        "grid": 208, "tile_km": 0.32,
        "center": (-157.015, 21.145),
        "km_per_lon": 103.85, "km_per_lat": 110.9,
        "outline": "data/coastlines/molokai.geojson",
        "ridges": [
            # East Molokaʻi shield (Kamakou), crest near the N sea cliffs
            ([(-156.97, 21.11), (-156.90, 21.11), (-156.83, 21.13),
              (-156.77, 21.15)], 3.2, 6.0, 0.9, 1.15),
            # West Molokaʻi dome (Maunaloa)
            ([(-157.23, 21.15), (-157.19, 21.13),
              (-157.15, 21.12)], 2.2, 3.6, 0.5, 0.5),
        ],
        "craters": [],
        "fields": [(-157.13, 21.11, -157.01, 21.18)],       # Hoʻolehua plain
        "core": None,
        "urban": "ua",
        "towns": [(-157.023, 21.089, 1.2),                  # Kaunakakai
                  (-157.216, 21.135, 0.7),                  # Maunaloa
                  (-157.070, 21.153, 0.7),                  # Kualapuʻu
                  (-156.985, 21.191, 0.5)],                 # Kalaupapa
        "bays": [(-157.26, 21.02, -156.78, 21.09)],         # south fringing reef
        "bays_tiles": [(-157.26, 21.02, -156.78, 21.09)],
        "rail": False,
        "home": "kaunakakai",
        "landmarks": [
            ("kaunakakai", "Kaunakakai", -157.023, 21.092, "town"),
            ("maunaloa", "Maunaloa", -157.216, 21.135, "town"),
            ("kualapuu", "Kualapuʻu", -157.070, 21.153, "town"),
            ("kalaupapa", "Kalaupapa", -156.978, 21.191, "poi"),
            ("kamakou", "Kamakou", -156.868, 21.108, "range"),
            ("halawa", "Hālawa", -156.740, 21.157, "nature"),
        ],
    },

    # ------------------------------------------------------------ Lānaʻi
    "lanai": {
        "name": "Lānaʻi",
        "grid": 128, "tile_km": 0.32,
        "center": (-156.93, 20.85),
        "km_per_lon": 104.0, "km_per_lat": 110.9,
        "outline": "data/coastlines/lanai.geojson",
        "ridges": [
            # Lānaʻihale crest
            ([(-156.91, 20.87), (-156.88, 20.83),
              (-156.85, 20.79)], 2.4, 4.4, 0.6, 0.75),
        ],
        "craters": [],
        "fields": [(-156.95, 20.76, -156.87, 20.83)],       # Pālāwai basin
        "core": None,
        "urban": "ua",
        "towns": [(-156.920, 20.828, 1.3)],                 # Lānaʻi City
        "bays": [],
        "bays_tiles": [],
        "rail": False,
        "home": "lanaicity",
        "landmarks": [
            ("lanaicity", "Lānaʻi City", -156.920, 20.828, "town"),
            ("lanaihale", "Lānaʻihale", -156.874, 20.812, "range"),
            ("manele", "Mānele Bay", -156.883, 20.744, "nature"),
        ],
    },

    # -------------------------------------------------------- Kahoʻolawe
    "kahoolawe": {
        "name": "Kahoʻolawe",
        "grid": 96, "tile_km": 0.32,
        "center": (-156.62, 20.545),
        "km_per_lon": 104.25, "km_per_lat": 110.9,
        "outline": "data/coastlines/kahoolawe.geojson",
        "ridges": [
            ([(-156.64, 20.56), (-156.60, 20.54),
              (-156.57, 20.53)], 1.6, 2.0, 0.3, 0.45),
        ],
        "craters": [],
        "fields": [],
        "core": None,
        "urban": "ua",
        "towns": [],
        "bays": [],
        "bays_tiles": [],
        "rail": False,
        "home": "moaulanui",
        "landmarks": [
            ("moaulanui", "Puʻu Moaulanui", -156.61, 20.555, "range"),
            ("kahoolawe", "Kahoʻolawe", -156.62, 20.51, "nature"),
        ],
    },

    # -------------------------------------------------------------- Maui
    "maui": {
        "name": "Maui",
        "grid": 288, "tile_km": 0.32,
        "center": (-156.335, 20.805),
        "km_per_lon": 104.06, "km_per_lat": 110.9,
        "outline": "data/coastlines/maui.geojson",
        "ridges": [
            # Haleakalā shield (crest with E + SW rift arms)
            ([(-156.23, 20.73), (-156.15, 20.71),
              (-156.08, 20.74)], 8.5, 15.0, 2.0, 1.9),
            # West Maui Mountains (Puʻu Kukui)
            ([(-156.63, 20.95), (-156.60, 20.90),
              (-156.56, 20.85)], 4.2, 7.0, 1.1, 1.25),
        ],
        "craters": [(-156.14, 20.715, 2.2, 4.6, 26)],       # Haleakalā crater
        "fields": [(-156.50, 20.80, -156.36, 20.92),        # central valley
                   (-156.35, 20.70, -156.24, 20.80)],       # Kula upcountry
        "core": None,
        "urban": "ua",
        "towns": [(-155.984, 20.758, 0.8)],                 # Hāna
        "bays": [],
        "bays_tiles": [],
        "rail": False,
        "home": "kahului",
        "landmarks": [
            ("wailuku", "Wailuku", -156.505, 20.891, "town"),
            ("kahului", "Kahului", -156.470, 20.885, "town"),
            ("lahaina", "Lāhainā", -156.674, 20.878, "town"),
            ("kihei", "Kīhei", -156.445, 20.765, "town"),
            ("makawao", "Makawao", -156.313, 20.857, "town"),
            ("hana", "Hāna", -155.984, 20.758, "town"),
            ("haleakala", "Haleakalā", -156.170, 20.710, "range"),
            ("westmaui", "West Maui Mountains", -156.590, 20.895, "range"),
        ],
    },

    # ----------------------------------------------------------- Hawaiʻi
    "hawaii": {
        "name": "Hawaiʻi",
        "grid": 336, "tile_km": 0.64,
        "center": (-155.43, 19.585),
        "km_per_lon": 104.9, "km_per_lat": 110.9,
        "outline": "data/coastlines/hawaii.geojson",
        "ridges": [
            # Mauna Kea
            ([(-155.48, 19.83), (-155.45, 19.80)], 11.0, 18.0, 2.2, 2.3),
            # Mauna Loa (summit + rift arms)
            ([(-155.78, 19.30), (-155.61, 19.47),
              (-155.47, 19.58)], 12.0, 19.0, 2.0, 2.2),
            # Kohala Mountains
            ([(-155.82, 20.02), (-155.75, 20.08),
              (-155.68, 20.15)], 4.5, 7.5, 1.0, 1.0),
            # Hualālai
            ([(-155.90, 19.72), (-155.85, 19.67)], 5.5, 9.0, 1.2, 1.3),
            # Kīlauea (with the East Rift toward Puna)
            ([(-155.29, 19.42), (-155.22, 19.39)], 3.5, 6.5, 0.6, 0.7),
        ],
        "craters": [(-155.605, 19.475, 1.2, 2.8, 30),       # Mokuʻāweoweo
                    (-155.287, 19.414, 1.3, 2.9, 12)],      # Kīlauea caldera
        "fields": [(-155.50, 19.95, -155.15, 20.12),        # Hāmākua coast
                   (-155.78, 19.98, -155.60, 20.05),        # Waimea plains
                   (-155.62, 19.05, -155.45, 19.20)],       # Kaʻū
        "core": None,
        "urban": "ua",
        "towns": [(-155.467, 20.079, 0.7),                  # Honokaʻa
                  (-155.585, 19.064, 0.6),                  # Nāʻālehu
                  (-154.945, 19.494, 0.7),                  # Pāhoa
                  (-155.932, 19.523, 0.9),                  # Kealakekua
                  (-155.234, 19.442, 0.7)],                 # Volcano
        "bays": [],
        "bays_tiles": [],
        "rail": False,
        "home": "hilo",
        "landmarks": [
            ("hilo", "Hilo", -155.090, 19.725, "town"),
            ("kona", "Kailua-Kona", -155.992, 19.640, "town"),
            ("waimea", "Waimea", -155.667, 20.023, "town"),
            ("pahoa", "Pāhoa", -154.945, 19.494, "town"),
            ("naalehu", "Nāʻālehu", -155.585, 19.064, "town"),
            ("maunakea", "Mauna Kea", -155.468, 19.821, "range"),
            ("maunaloa2", "Mauna Loa", -155.608, 19.475, "range"),
            ("kilauea", "Kīlauea", -155.287, 19.421, "nature"),
            ("kohala", "Kohala Mountains", -155.735, 20.086, "range"),
            ("hualalai", "Hualālai", -155.870, 19.689, "range"),
        ],
    },
}

# west-to-east order for the in-game island switcher
ORDER = ["niihau", "kauai", "oahu", "molokai", "lanai", "kahoolawe",
         "maui", "hawaii"]
