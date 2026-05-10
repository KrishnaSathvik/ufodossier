"use client";

import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { MapPanel } from "@/components/MapPanel";

function rasterStyle(variant: "dark_all" | "light_all"): maplibregl.StyleSpecification {
  return {
    version: 8,
    sources: {
      carto: {
        type: "raster",
        tiles: [
          `https://a.basemaps.cartocdn.com/${variant}/{z}/{x}/{y}@2x.png`,
          `https://b.basemaps.cartocdn.com/${variant}/{z}/{x}/{y}@2x.png`,
          `https://c.basemaps.cartocdn.com/${variant}/{z}/{x}/{y}@2x.png`,
          `https://d.basemaps.cartocdn.com/${variant}/{z}/{x}/{y}@2x.png`,
        ],
        tileSize: 256,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
      },
    },
    glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
    layers: [{ id: "carto-basemap", type: "raster", source: "carto" }],
  };
}

function getMapStyle(): maplibregl.StyleSpecification {
  return document.documentElement.classList.contains("dark")
    ? rasterStyle("dark_all")
    : rasterStyle("light_all");
}

export interface MapIncident {
  id: string;
  title: string;
  occurred_at: string | null;
  occurred_at_text: string | null;
  branch: string | null;
  location_text: string | null;
  lat: number;
  lon: number;
  resolution_status: string | null;
  case_id: string;
  summary: string | null;
  raw_excerpt: string | null;
  sensor_types: string[] | null;
  country: string | null;
  image_url: string | null;
  video_url: string | null;
  cover_image_url: string | null;
  source_cover_image_url: string | null;
}

function toGeoJSON(incidents: MapIncident[]): GeoJSON.FeatureCollection {
  // Jitter overlapping coordinates so stacked dots spread out when unclustered
  const seen = new Map<string, number>();
  const OFFSET = 0.04; // ~4km at equator — enough to visually separate at high zoom

  return {
    type: "FeatureCollection",
    features: incidents.map((inc) => {
      const key = `${inc.lat.toFixed(4)},${inc.lon.toFixed(4)}`;
      const count = seen.get(key) || 0;
      seen.set(key, count + 1);

      let lon = inc.lon;
      let lat = inc.lat;
      if (count > 0) {
        const angle = (count * 2 * Math.PI) / 6; // spread in a hex pattern
        lon += OFFSET * Math.cos(angle);
        lat += OFFSET * Math.sin(angle);
      }

      return {
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [lon, lat],
        },
        properties: {
          id: inc.id,
          title: inc.title,
          status: inc.resolution_status,
        },
      };
    }),
  };
}

function addSourceAndLayers(map: maplibregl.Map, incidents: MapIncident[]) {
  const isDark = document.documentElement.classList.contains("dark");

  map.addSource("incidents", {
    type: "geojson",
    data: toGeoJSON(incidents),
    cluster: true,
    clusterMaxZoom: 13,
    clusterRadius: 30,
  });

  // Cluster circles — amber glow
  map.addLayer({
    id: "clusters",
    type: "circle",
    source: "incidents",
    filter: ["has", "point_count"],
    paint: {
      "circle-color": "#ff9933",
      "circle-radius": ["step", ["get", "point_count"], 16, 10, 22, 50, 30],
      "circle-opacity": 0.8,
      "circle-blur": 0.15,
    },
  });

  // Cluster count labels
  map.addLayer({
    id: "cluster-count",
    type: "symbol",
    source: "incidents",
    filter: ["has", "point_count"],
    layout: {
      "text-field": "{point_count_abbreviated}",
      "text-font": ["Noto Sans Regular"],
      "text-size": 12,
      "text-allow-overlap": true,
    },
    paint: {
      "text-color": isDark ? "#0a0a0a" : "#ffffff",
    },
  });

  // Individual incident dots
  map.addLayer({
    id: "incident-dots",
    type: "circle",
    source: "incidents",
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-color": [
        "match",
        ["get", "status"],
        "unresolved", "#c8302a",
        "identified", "#66aa88",
        "#888888",
      ],
      "circle-radius": 7,
      "circle-stroke-width": 1.5,
      "circle-stroke-color": isDark ? "#0a0a0a" : "#ffffff",
      "circle-opacity": 0.9,
    },
  });

  // Dot pulse ring for unresolved
  map.addLayer({
    id: "incident-pulse",
    type: "circle",
    source: "incidents",
    filter: ["all",
      ["!", ["has", "point_count"]],
      ["==", ["get", "status"], "unresolved"],
    ],
    paint: {
      "circle-color": "#c8302a",
      "circle-radius": 14,
      "circle-opacity": 0.15,
      "circle-blur": 1,
    },
  });
}

export function MapView({ incidents }: { incidents: MapIncident[] }) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const sourceReady = useRef(false);
  const incidentsRef = useRef(incidents);
  incidentsRef.current = incidents;
  const [selected, setSelected] = useState<MapIncident | null>(null);

  // Create map once
  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: getMapStyle(),
      center: [-98, 39],
      zoom: 4,
      maxZoom: 14,
    });

    // Only show zoom controls on desktop
    if (window.matchMedia("(min-width: 768px)").matches) {
      map.addControl(new maplibregl.NavigationControl(), "top-left");
    }

    map.on("load", () => {
      addSourceAndLayers(map, incidentsRef.current);
      sourceReady.current = true;

      // Auto-fit to incident bounds
      if (incidentsRef.current.length > 1) {
        const bounds = new maplibregl.LngLatBounds();
        incidentsRef.current.forEach((inc) => bounds.extend([inc.lon, inc.lat]));
        map.fitBounds(bounds, { padding: 60, maxZoom: 6 });
      }
    });

    // Unified click: check dots first (with touch-friendly bbox), then clusters
    const isTouchDevice = "ontouchstart" in window;
    const TAP_TOLERANCE = isTouchDevice ? 20 : 5;

    map.on("click", (e) => {
      const bbox: [maplibregl.PointLike, maplibregl.PointLike] = [
        [e.point.x - TAP_TOLERANCE, e.point.y - TAP_TOLERANCE],
        [e.point.x + TAP_TOLERANCE, e.point.y + TAP_TOLERANCE],
      ];

      // Prioritize individual dots over clusters
      const dots = map.queryRenderedFeatures(bbox, { layers: ["incident-dots"] });
      if (dots.length) {
        const id = dots[0].properties.id;
        const inc = incidentsRef.current.find((i) => i.id === id);
        if (inc) setSelected(inc);
        return;
      }

      // Then check clusters
      const clusters = map.queryRenderedFeatures(bbox, { layers: ["clusters"] });
      if (clusters.length) {
        const clusterId = clusters[0].properties.cluster_id;
        const source = map.getSource("incidents") as maplibregl.GeoJSONSource;
        source.getClusterExpansionZoom(clusterId).then((expansionZoom) => {
          const currentZoom = map.getZoom();
          // If we can't zoom in further (already at or past expansion zoom), show first incident
          if (expansionZoom <= currentZoom + 0.5) {
            source.getClusterLeaves(clusterId, 10, 0).then((leaves) => {
              if (leaves?.length) {
                const id = leaves[0].properties?.id;
                const inc = incidentsRef.current.find((i) => i.id === id);
                if (inc) setSelected(inc);
              }
            }).catch(() => {});
          } else {
            const geom = clusters[0].geometry as GeoJSON.Point;
            map.easeTo({ center: geom.coordinates as [number, number], zoom: expansionZoom });
          }
        });
      }
    });

    // Cursor changes (desktop only)
    map.on("mouseenter", "clusters", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "clusters", () => { map.getCanvas().style.cursor = ""; });
    map.on("mouseenter", "incident-dots", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "incident-dots", () => { map.getCanvas().style.cursor = ""; });

    mapRef.current = map;

    // Watch for theme changes (dark class toggled on <html>)
    const observer = new MutationObserver(() => {
      if (!mapRef.current) return;
      const newStyle = getMapStyle();
      const center = mapRef.current.getCenter();
      const zoom = mapRef.current.getZoom();
      mapRef.current.setStyle(newStyle);
      // Re-add source + layers after style swap
      mapRef.current.once("style.load", () => {
        addSourceAndLayers(mapRef.current!, incidentsRef.current);
        mapRef.current!.setCenter(center);
        mapRef.current!.setZoom(zoom);
      });
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

    return () => {
      observer.disconnect();
      map.remove();
      mapRef.current = null;
      sourceReady.current = false;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update GeoJSON source when incidents change (filtering)
  useEffect(() => {
    if (!mapRef.current || !sourceReady.current) return;
    const source = mapRef.current.getSource("incidents") as maplibregl.GeoJSONSource;
    if (source) {
      source.setData(toGeoJSON(incidents));
    }
  }, [incidents]);

  function handleClose() {
    setSelected(null);
    // Zoom out to fit all incidents
    if (mapRef.current && incidentsRef.current.length > 1) {
      const bounds = new maplibregl.LngLatBounds();
      incidentsRef.current.forEach((inc) => bounds.extend([inc.lon, inc.lat]));
      mapRef.current.fitBounds(bounds, { padding: 60, maxZoom: 6, duration: 800 });
    }
  }

  return (
    <div className="relative w-full h-full">
      <div ref={mapContainer} className="w-full h-full" />

      {selected && (
        <MapPanel incident={selected} onClose={handleClose} />
      )}
    </div>
  );
}
