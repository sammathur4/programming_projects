import { useEffect, useMemo, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const colors = {
  airbase: '#a64d3b', city: '#315d70', state: '#9b6a2f', district: '#89703d',
  river: '#397a91', sea: '#397a91', island: '#658052', peninsula: '#658052',
  volcano: '#a64d3b', country: '#565e70', sanctuary: '#4d7a56',
}
const topicTitles = {
  'nyoma-airbase': 'Nyoma Airbase', 'siddi-community': 'Siddi Community',
  'naseem-al-bahr': 'Exercise Naseem Al Bahr', 'begonia-siangensis': 'Begonia siangensis',
  'bherjan-sanctuary': 'Bherjan-Borajan-Padumoni Sanctuary', 'chinar-kashmir': 'Chinar and Kashmir',
  'rahat-mitra': 'Exercise RAHAT MITRA', 'gulf-california': 'Gulf of California',
  kilauea: 'Kīlauea Volcano', 'ramon-magsaysay': 'Ramon Magsaysay Award',
  'india-bangladesh-jrc': 'India–Bangladesh Joint Rivers Commission', 'apec-shenzhen': 'APEC 2026 in Shenzhen',
}
const noop = () => {}

function placeIsIndia(place) {
  return place.country === 'India'
}

function markerPopup(place, onOpenTopic) {
  const box = document.createElement('div')
  box.className = 'ca-map-popup'
  const title = document.createElement('strong')
  title.textContent = place.name
  const detail = document.createElement('p')
  detail.textContent = `${[place.state, place.country].filter(Boolean).join(', ')} · ${place.confidence}`
  box.append(title, detail)
  const description = document.createElement('p')
  description.textContent = place.description
  box.append(description)
  for (const id of place.relatedTopics) {
    const link = document.createElement('a')
    link.href = `#${id}`
    link.textContent = `Open ${topicTitles[id] || id}`
    link.addEventListener('click', (event) => {
      event.preventDefault()
      onOpenTopic(id)
    })
    box.append(link)
  }
  return box
}

export default function AtlasMap({ locations, title = 'Revision atlas', locationIds, onOpenTopic = noop }) {
  const container = useRef(null)
  const map = useRef(null)
  const markers = useRef(null)
  const [region, setRegion] = useState(locationIds ? 'all' : 'india')
  const [category, setCategory] = useState('all')
  const [query, setQuery] = useState('')
  const [tileError, setTileError] = useState(false)

  const categories = useMemo(() => [...new Set(locations.map((place) => place.category))].sort(), [locations])
  const visible = useMemo(() => locations.filter((place) => {
    const regionMatches = region === 'all' || (region === 'india' ? placeIsIndia(place) : !placeIsIndia(place))
    const categoryMatches = category === 'all' || place.category === category
    const text = `${place.name} ${place.state} ${place.country} ${place.description}`.toLowerCase()
    return regionMatches && categoryMatches && text.includes(query.toLowerCase())
  }), [locations, region, category, query])
  const unmapped = visible.filter((place) => !Number.isFinite(place.latitude) || !Number.isFinite(place.longitude))

  useEffect(() => {
    if (!container.current || map.current) return undefined
    const instance = L.map(container.current, { scrollWheelZoom: false, zoomControl: true }).setView([24, 78], 4)
    const tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
    }).addTo(instance)
    tiles.on('tileerror', () => setTileError(true))
    markers.current = L.layerGroup().addTo(instance)
    map.current = instance
    const resize = new ResizeObserver(() => instance.invalidateSize())
    resize.observe(container.current)
    return () => {
      resize.disconnect()
      instance.remove()
      map.current = null
      markers.current = null
    }
  }, [])

  useEffect(() => {
    if (!map.current || !markers.current) return
    markers.current.clearLayers()
    const plotted = visible.filter((place) => Number.isFinite(place.latitude) && Number.isFinite(place.longitude))
    for (const place of plotted) {
      const marker = L.circleMarker([place.latitude, place.longitude], {
        radius: place.category === 'state' || place.category === 'district' ? 8 : 7,
        color: '#fff', weight: 2, fillColor: colors[place.category] || '#42635f', fillOpacity: 0.95,
      })
      marker.bindPopup(markerPopup(place, onOpenTopic), { maxWidth: 260 })
      marker.addTo(markers.current)
    }
    if (plotted.length > 1) {
      map.current.fitBounds(L.latLngBounds(plotted.map((place) => [place.latitude, place.longitude])), { padding: [28, 28], maxZoom: 8 })
    } else if (plotted.length === 1) {
      map.current.setView([plotted[0].latitude, plotted[0].longitude], 8)
    }
  }, [visible, onOpenTopic])

  const resetView = () => {
    setRegion(locationIds ? 'all' : 'india')
    setCategory('all')
    setQuery('')
  }

  return (
    <section className="ca-atlas-card" aria-label={title}>
      <div className="ca-atlas-head">
        <div><span className="ca-eyebrow">GEOGRAPHICAL CONTEXT</span><h3>{title}</h3></div>
        <button type="button" className="ca-quiet-button" onClick={resetView}>Reset map</button>
      </div>
      <div className="ca-map-controls">
        <label>Region<select value={region} onChange={(event) => setRegion(event.target.value)}>
          <option value="all">All regions</option><option value="india">India</option><option value="world">International</option>
        </select></label>
        <label>Category<select value={category} onChange={(event) => setCategory(event.target.value)}>
          <option value="all">All categories</option>{categories.map((item) => <option key={item} value={item}>{item}</option>)}
        </select></label>
        <label className="ca-map-search">Find a place<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search this map" /></label>
        <button type="button" className="ca-quiet-button" onClick={() => {
          const bounds = markers.current?.getBounds()
          if (bounds?.isValid()) map.current?.fitBounds(bounds, { padding: [28, 28], maxZoom: 8 })
        }}>Fit places</button>
      </div>
      {tileError && <p className="ca-map-fallback" role="status">Map tiles are unavailable. Markers and place details remain listed below.</p>}
      <div className="ca-map" ref={container} role="application" aria-label={`${title}, interactive OpenStreetMap`} />
      <div className="ca-map-legend" aria-label="Map legend">
        {Object.entries(colors).filter(([key]) => categories.includes(key)).map(([key, color]) => (
          <span key={key}><i style={{ backgroundColor: color }} />{key}</span>
        ))}
      </div>
      <details className="ca-place-list" open={unmapped.length > 0}>
        <summary>{visible.length} locations · {unmapped.length} without a verified point</summary>
        <ul>{visible.map((place) => <li key={place.id}>
          <strong>{place.name}</strong> <span>{place.state || place.country}</span>
          {place.confidence === 'unavailable' && <em>Not plotted: no reliable geocode or boundary found.</em>}
        </li>)}</ul>
      </details>
      <small className="ca-map-attribution">Map tiles © OpenStreetMap contributors. Place points are geocoded references; state centres and other approximate points are not boundaries. LAC and vaquita habitat boundaries are not drawn.</small>
    </section>
  )
}
