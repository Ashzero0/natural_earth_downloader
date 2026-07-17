# -*- coding: utf-8 -*-
"""Curated Natural Earth vector catalogue.

The plugin deliberately uses stable direct archive URLs instead of scraping the
Natural Earth website. Add or remove entries in THEMES to evolve the catalogue.
"""

BASE_URL = "https://naturalearth.s3.amazonaws.com"

SCALE_LABELS = {
    "10m": "1:10m",
    "50m": "1:50m",
    "110m": "1:110m",
}


def _entry(scale, category, slug, name, geometry, description, tags=""):
    dataset_id = f"ne_{scale}_{slug}"
    folder = f"{scale}_{category.lower()}"
    return {
        "id": dataset_id,
        "scale": scale,
        "scale_label": SCALE_LABELS[scale],
        "category": category,
        "slug": slug,
        "name": name,
        "geometry": geometry,
        "description": description,
        "tags": tags,
        "url": f"{BASE_URL}/{folder}/{dataset_id}.zip",
        "archive": f"{dataset_id}.zip",
    }


THEMES = [
    # slug, friendly name, category, geometry, scales, description, tags
    ("admin_0_countries", "Countries", "Cultural", "Polygon", ["10m", "50m", "110m"],
     "Country polygons with names, codes, regions, population and economic attributes.",
     "admin boundaries nations states world"),
    ("admin_0_map_units", "Map units", "Cultural", "Polygon", ["10m", "50m", "110m"],
     "Administrative map units, including dependent overseas areas separated from sovereign states.",
     "admin dependencies overseas territories"),
    ("admin_0_sovereignty", "Sovereign states", "Cultural", "Polygon", ["10m", "50m", "110m"],
     "Sovereign-state polygons grouping dependent territories with their sovereign country.",
     "admin sovereignty countries"),
    ("admin_0_boundary_lines_land", "Country boundary lines", "Cultural", "Line", ["10m", "50m", "110m"],
     "International land boundary lines suitable for cartographic display.",
     "borders boundaries admin"),
    ("admin_0_boundary_lines_disputed_areas", "Disputed boundary lines", "Cultural", "Line", ["10m", "50m", "110m"],
     "Boundary lines for disputed areas and special sovereignty situations.",
     "disputed borders boundaries"),
    ("admin_1_states_provinces", "States and provinces", "Cultural", "Polygon", ["10m", "50m"],
     "First-order administrative divisions such as states, regions and provinces.",
     "admin1 regions provinces departments"),
    ("admin_1_states_provinces_lines", "State and province boundaries", "Cultural", "Line", ["10m", "50m"],
     "Boundary lines for first-order administrative divisions.",
     "admin1 boundaries regions provinces"),
    ("populated_places", "Populated places", "Cultural", "Point", ["10m", "50m", "110m"],
     "Cities and towns ranked for display, with names and population-related attributes.",
     "cities towns capitals population places"),
    ("urban_areas", "Urban areas", "Cultural", "Polygon", ["10m", "50m", "110m"],
     "Generalized polygons representing urbanized areas.",
     "cities settlements built up urban"),
    ("roads", "Roads", "Cultural", "Line", ["10m"],
     "Major global road network generalized for small-scale mapping.",
     "transport highways routes"),
    ("railroads", "Railroads", "Cultural", "Line", ["10m"],
     "Major global railway lines generalized for small-scale mapping.",
     "transport train railway"),
    ("airports", "Airports", "Cultural", "Point", ["10m"],
     "Major airports with names, codes and scale-ranking attributes.",
     "transport aviation airport iata"),
    ("ports", "Ports", "Cultural", "Point", ["10m"],
     "Major world ports and harbours.",
     "transport maritime harbour shipping"),
    ("time_zones", "Time zones", "Cultural", "Polygon", ["10m"],
     "Global time-zone polygons for cartographic and reference use.",
     "timezone utc time"),
    ("parks_and_protected_lands_area", "Protected areas", "Cultural", "Polygon", ["10m"],
     "Selected parks and protected lands represented as polygons.",
     "parks nature conservation protected"),
    ("parks_and_protected_lands_line", "Protected area lines", "Cultural", "Line", ["10m"],
     "Selected protected-land features represented as lines.",
     "parks nature conservation protected"),
    ("parks_and_protected_lands_point", "Protected area points", "Cultural", "Point", ["10m"],
     "Selected parks and protected lands represented as points.",
     "parks nature conservation protected"),

    ("land", "Land", "Physical", "Polygon", ["10m", "50m", "110m"],
     "Global land polygons, including major islands appropriate to the selected scale.",
     "land continents islands base map"),
    ("ocean", "Ocean", "Physical", "Polygon", ["10m", "50m", "110m"],
     "Global ocean polygon suitable as a map background.",
     "water ocean sea base map"),
    ("coastline", "Coastline", "Physical", "Line", ["10m", "50m", "110m"],
     "Global coastline lines generalized for the selected scale.",
     "shore coast land sea"),
    ("lakes", "Lakes", "Physical", "Polygon", ["10m", "50m", "110m"],
     "Major lake polygons with scale-ranking and naming attributes.",
     "water inland lakes reservoirs"),
    ("rivers_lake_centerlines", "Rivers and lake centerlines", "Physical", "Line", ["10m", "50m", "110m"],
     "Major rivers and lake centerlines, ranked for cartographic display.",
     "water hydrography river stream"),
    ("geographic_lines", "Geographic reference lines", "Physical", "Line", ["10m", "50m", "110m"],
     "Named geographic reference lines such as tropics, circles and the Equator.",
     "equator tropics arctic antarctic reference"),
    ("geography_regions_points", "Geographic region labels", "Physical", "Point", ["10m", "50m", "110m"],
     "Point locations for geographic region labels such as deserts, plateaus and basins.",
     "labels regions geography"),
    ("geography_regions_polys", "Geographic regions", "Physical", "Polygon", ["10m", "50m", "110m"],
     "Polygon areas for selected named geographic regions.",
     "regions geography deserts basins"),
    ("geography_marine_polys", "Marine geographic regions", "Physical", "Polygon", ["10m", "50m", "110m"],
     "Named marine regions, seas, bays, straits and ocean subdivisions.",
     "marine seas bays straits oceans"),
    ("minor_islands", "Minor islands", "Physical", "Polygon", ["10m", "50m"],
     "Small island polygons omitted from the standard land theme at some scales.",
     "islands land minor"),
    ("reefs", "Reefs", "Physical", "Polygon", ["10m"],
     "Selected major coral and marine reef polygons.",
     "coral reef marine"),
    ("glaciated_areas", "Glaciated areas", "Physical", "Polygon", ["10m", "50m"],
     "Major glaciers and permanently glaciated land areas.",
     "glacier ice snow"),
    ("antarctic_ice_shelves_polys", "Antarctic ice shelves", "Physical", "Polygon", ["10m", "50m"],
     "Antarctic ice-shelf polygons.",
     "antarctica ice shelves"),
    ("antarctic_ice_shelves_lines", "Antarctic ice-shelf lines", "Physical", "Line", ["10m", "50m"],
     "Antarctic ice-shelf edge lines.",
     "antarctica ice shelves lines"),
]


def build_catalogue():
    items = []
    for slug, name, category, geometry, scales, description, tags in THEMES:
        for scale in scales:
            items.append(_entry(scale, category, slug, name, geometry, description, tags))
    items.sort(key=lambda d: (d["category"], d["name"].lower(), {"10m": 0, "50m": 1, "110m": 2}[d["scale"]]))
    return items


CATALOGUE = build_catalogue()
