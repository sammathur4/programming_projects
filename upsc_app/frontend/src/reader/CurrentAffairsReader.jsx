import { useCallback, useEffect, useId, useMemo, useState } from 'react'
import DOMPurify from 'dompurify'
import source from '../data/2026-11-11.md?raw'
import geoData from '../data/locations.json'
import AtlasMap from './AtlasMap.jsx'
import { diagramsFor } from './diagrams.js'
import { matchLocations, parseDocument, relationships, revisionFacts, topicGroups } from './document.js'
import './CurrentAffairsReader.css'

const STORAGE = 'iascode-ca-atlas-2026-11-11'
const safeRead = (key, fallback) => {
  try { return JSON.parse(localStorage.getItem(`${STORAGE}-${key}`)) ?? fallback } catch { return fallback }
}

function loadMermaid() {
  if (window.mermaid) return Promise.resolve(window.mermaid)
  if (window.__iasMermaid) return window.__iasMermaid
  window.__iasMermaid = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js'
    script.async = true
    script.onload = () => resolve(window.mermaid)
    script.onerror = () => reject(new Error('Mermaid is unavailable'))
    document.head.append(script)
  })
  return window.__iasMermaid
}

function MermaidDiagram({ title, chart }) {
  const [svg, setSvg] = useState('')
  const [error, setError] = useState(false)
  const id = `diagram-${useId().replace(/:/g, '')}`
  useEffect(() => {
    let active = true
    loadMermaid().then(async (mermaid) => {
      mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'base', themeVariables: {
        primaryColor: '#edf2ec', primaryTextColor: '#203a36', primaryBorderColor: '#b8c8ba',
        lineColor: '#7f968c', secondaryColor: '#f7f4ed', tertiaryColor: '#fff',
      } })
      const rendered = await mermaid.render(id, chart)
      if (active) setSvg(DOMPurify.sanitize(rendered.svg, { USE_PROFILES: { svg: true, svgFilters: true } }))
    }).catch(() => active && setError(true))
    return () => { active = false }
  }, [chart, id])
  return <figure className="ca-diagram"><figcaption>{title}</figcaption>{svg
    ? <div className="ca-diagram-svg" dangerouslySetInnerHTML={{ __html: svg }} />
    : error ? <pre className="ca-diagram-fallback"><code>{chart}</code></pre> : <div className="ca-diagram-loading">Loading diagram…</div>}
  </figure>
}

function TopicMap({ onJump }) {
  return <div className="ca-topic-map" aria-label="Clickable topic mind map">
    {topicGroups.map((group) => <div className="ca-topic-branch" key={group.title}>
      <strong>{group.title}</strong>
      <ul>{group.topics.map((topic) => <li key={topic}><button onClick={() => onJump(topic)}>{topic}</button></li>)}</ul>
    </div>)}
  </div>
}

function Highlighted({ text, query }) {
  if (!query) return text
  const pieces = text.split(new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'ig'))
  return pieces.map((piece, index) => piece.toLowerCase() === query.toLowerCase()
    ? <mark key={index}>{piece}</mark> : piece)
}

function topicTarget(fact, sections) {
  const pattern = fact.includes('Education') ? /national education day/i
    : fact.includes('Dakar') ? /siddi|khushbu/i
      : fact.includes('Nyoma') ? /nyoma airbase/i
        : fact.includes('Naseem') ? /naseem al bahr/i
          : fact.includes('Anaemia') ? /^anaemia$/i
            : fact.includes('VAJRA') ? /vajra.sat/i
              : fact.includes('Muhurat') ? /muhurat trading/i
                : fact.includes('RAHAT') ? /rahat mitra/i
                  : fact.includes('Kīlauea') ? /kīlauea|hawai/i
                    : /apec|shenzhen/i
  return sections.find((section) => pattern.test(section.title))?.id || sections[0]?.id
}

export default function CurrentAffairsReader() {
  const documentModel = useMemo(() => parseDocument(source), [])
  const [query, setQuery] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)
  const [mobileNav, setMobileNav] = useState(false)
  const [revisionMode, setRevisionMode] = useState(false)
  const [theme, setTheme] = useState(() => localStorage.getItem(`${STORAGE}-theme`) || 'light')
  const [bookmarks, setBookmarks] = useState(() => safeRead('bookmarks', []))
  const [notes, setNotes] = useState(() => safeRead('notes', {}))
  const [progress, setProgress] = useState(0)
  const [toast, setToast] = useState('')

  useEffect(() => {
    window.document.title = '11 November 2026 · UPSC Current Affairs Atlas'
    window.document.documentElement.dataset.caTheme = theme
    localStorage.setItem(`${STORAGE}-theme`, theme)
    return () => { delete window.document.documentElement.dataset.caTheme }
  }, [theme])

  useEffect(() => {
    const update = () => {
      const scrollable = window.document.documentElement.scrollHeight - window.innerHeight
      setProgress(scrollable > 0 ? Math.min(100, Math.round((window.scrollY / scrollable) * 100)) : 0)
    }
    update()
    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update)
    return () => { window.removeEventListener('scroll', update); window.removeEventListener('resize', update) }
  }, [])

  useEffect(() => {
    const keydown = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setSearchOpen(true)
        window.document.querySelector('.ca-search-input')?.focus()
      }
      if (event.key === 'Escape') { setSearchOpen(false); setMobileNav(false) }
    }
    window.addEventListener('keydown', keydown)
    return () => window.removeEventListener('keydown', keydown)
  }, [])

  const results = useMemo(() => {
    const term = query.trim().toLowerCase()
    if (!term) return []
    return documentModel.sections.filter((section) => `${section.title} ${section.text}`.toLowerCase().includes(term)).slice(0, 12)
  }, [documentModel, query])

  const jump = useCallback((id) => {
    let target = window.document.getElementById(id)
    if (!target) target = window.document.querySelector(`[data-topic-id="${id}"]`)
    if (!target && typeof id === 'string') {
      const section = documentModel.sections.find((item) => item.title.toLowerCase().includes(id.toLowerCase()))
      if (section) target = window.document.getElementById(section.id)
    }
    if (!target && typeof id === 'string') {
      const section = documentModel.sections.find((item) => item.locationIds.includes(id))
      if (section) target = window.document.getElementById(section.id)
    }
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' })
      if (target.id) history.replaceState(null, '', `#${target.id}`)
      setMobileNav(false)
      setSearchOpen(false)
    }
  }, [documentModel])

  const matchingSections = useCallback((topicTitle) => {
    const text = topicTitle.toLowerCase()
    const matches = documentModel.sections.filter((section) => `${section.title} ${section.text}`.toLowerCase().includes(text))
    return matches[0]
  }, [documentModel])

  const toggleBookmark = (id) => {
    setBookmarks((items) => {
      const next = items.includes(id) ? items.filter((item) => item !== id) : [...items, id]
      localStorage.setItem(`${STORAGE}-bookmarks`, JSON.stringify(next))
      return next
    })
  }
  const saveNote = (id, value) => {
    setNotes((current) => {
      const next = { ...current, [id]: value }
      localStorage.setItem(`${STORAGE}-notes`, JSON.stringify(next))
      return next
    })
  }
  const copyLink = async (id) => {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/atlas#${id}`)
      setToast('Deep link copied')
    } catch { setToast('Select and copy the section URL from the address bar') }
    window.setTimeout(() => setToast(''), 2400)
  }

  const nav = <aside className={`ca-sidebar ${mobileNav ? 'is-open' : ''}`}>
    <div className="ca-brand-row"><a href="/" className="ca-brand"><span>i</span> IASCode</a><button className="ca-mobile-close" onClick={() => setMobileNav(false)} aria-label="Close navigation">×</button></div>
    <div className="ca-sidebar-title"><small>STUDY ATLAS</small><strong>11 November 2026</strong></div>
    <label className="ca-search-wrap"><span>Search document</span><input className="ca-search-input" value={query} onChange={(event) => { setQuery(event.target.value); setSearchOpen(true) }} placeholder="Topic, place, fact…" /><kbd>Ctrl K</kbd></label>
    {searchOpen && query.trim() && <div className="ca-search-results">
      <div className="ca-search-count">{results.length} matching sections</div>
      {results.map((section) => <button key={section.id} onClick={() => jump(section.id)}><strong>{section.title}</strong><span><Highlighted text={section.text.slice(0, 130)} query={query} /></span></button>)}
      {!results.length && <p>No matches in this document.</p>}
    </div>}
    <nav className="ca-toc" aria-label="Document contents">
      <div className="ca-toc-label">ON THIS PAGE</div>
      {documentModel.sections.map((section) => <button key={section.id} className={`ca-toc-link level-${section.level}`} onClick={() => jump(section.id)} title={section.title}>{section.title}</button>)}
      <button className="ca-toc-link ca-toc-atlas" onClick={() => jump('revision-atlas')}>Revision Atlas</button>
    </nav>
    <div className="ca-sidebar-bottom"><span>{progress}% read</span><div><i style={{ width: `${progress}%` }} /></div><a href="/">← Back to question bank</a></div>
  </aside>

  return <div className={`ca-reader ${revisionMode ? 'revision-mode' : ''}`}>
    {nav}
    {mobileNav && <button className="ca-mobile-scrim" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}
    <div className="ca-reader-main">
      <header className="ca-topbar">
        <button className="ca-mobile-menu" onClick={() => setMobileNav(true)} aria-label="Open navigation">☰</button>
        <div className="ca-crumb"><a href="/">IASCode</a><span>/</span><strong>Current Affairs</strong></div>
        <div className="ca-top-actions">
          <button onClick={() => setRevisionMode((value) => !value)}>{revisionMode ? 'Full document' : 'Revision mode'}</button>
          <button onClick={() => setTheme((value) => value === 'light' ? 'dark' : 'light')}>{theme === 'light' ? 'Dark mode' : 'Light mode'}</button>
          <button onClick={() => window.print()}>Print</button>
        </div>
      </header>
      <div className="ca-progress"><i style={{ width: `${progress}%` }} /></div>

      <div className="ca-layout">
        <main className="ca-main-content">
          <header className="ca-document-head">
            <div className="ca-eyebrow">CURRENT AFFAIRS · PRELIMS + MAINS</div>
            <h1>{documentModel.title}</h1>
            <p className="ca-deck">A structured reading view of the supplied source note. Original facts and explanations are retained.</p>
            <div className="ca-meta"><span>11 Nov 2026</span><span>Reading time ~18 min</span><span>Source: daily current-affairs note</span></div>
          </header>

          {revisionMode ? <RevisionView onJump={(fact) => jump(topicTarget(fact, documentModel.sections))} onTopic={jump} locations={geoData.locations} /> : (
            <article className="ca-article">
              <div className="ca-source-note"><strong>Reading note</strong><span>This view reorganises headings, lists and the haemoglobin table for readability. It does not fact-check or paraphrase the source.</span></div>
              {documentModel.sections.map((section) => <ArticleSection key={section.id} section={section} locations={geoData.locations} bookmarks={bookmarks} notes={notes} onBookmark={toggleBookmark} onSaveNote={saveNote} onCopy={copyLink} onJump={jump} />)}
              <details className="ca-raw-source"><summary>View preserved source text</summary><pre>{source}</pre></details>
            </article>
          )}

          <section className="ca-atlas-section" id="revision-atlas">
            <div className="ca-section-heading"><div><span className="ca-eyebrow">INTERACTIVE GEOGRAPHY</span><h2>Revision Atlas</h2></div><span className="ca-pill">OpenStreetMap</span></div>
            <p>Explore the named locations in the source. Approximate reference points are labelled; disputed boundaries and unavailable sanctuary boundaries are not drawn.</p>
            <AtlasMap locations={geoData.locations} onOpenTopic={jump} />
          </section>

          <section className="ca-graph-section">
            <div className="ca-section-heading"><div><span className="ca-eyebrow">CONTEXTUAL CONNECTIONS</span><h2>Topic mind map</h2></div></div>
            <TopicMap onJump={(title) => { const section = matchingSections(title); if (section) jump(section.id); else { setQuery(title); setSearchOpen(true); window.scrollTo({ top: 0, behavior: 'smooth' }) } }} />
          </section>
        </main>

        <aside className="ca-context-rail">
          <section className="ca-rail-card"><span className="ca-eyebrow">QUICK REVISION</span><h2>Key facts</h2><div className="ca-fact-list">{revisionFacts.slice(0, 6).map(([type, text]) => <button key={type} onClick={() => jump(topicTarget(text, documentModel.sections))}><small>{type}</small><span>{text}</span></button>)}</div><button className="ca-inline-link" onClick={() => setRevisionMode(true)}>Open full revision view →</button></section>
          <section className="ca-rail-card"><span className="ca-eyebrow">BOOKMARKS</span><h2>Saved topics</h2>{bookmarks.length ? bookmarks.map((id) => { const item = documentModel.sections.find((section) => section.id === id); return item && <button className="ca-saved-topic" key={id} onClick={() => jump(id)}>{item.title}</button> }) : <p className="ca-muted">Bookmark a section to find it here.</p>}</section>
          <section className="ca-rail-card"><span className="ca-eyebrow">KNOWLEDGE GRAPH</span><h2>Connections</h2>{relationships.slice(0, 5).map(([name, links]) => <details className="ca-relation" key={name}><summary>{name}</summary><div>{links.map((link) => <button key={link} onClick={() => { setQuery(link); setSearchOpen(true); window.scrollTo({ top: 0, behavior: 'smooth' }) }}>{link}</button>)}</div></details>)}</section>
          <section className="ca-rail-card ca-rail-map"><span className="ca-eyebrow">PLACE INDEX</span><h2>Locations</h2><div>{geoData.locations.filter((location) => location.latitude !== null).slice(0, 8).map((place) => <button key={place.id} onClick={() => jump(place.relatedTopics[0])}>{place.name}</button>)}</div><button className="ca-inline-link" onClick={() => jump('revision-atlas')}>Open interactive atlas →</button></section>
        </aside>
      </div>
      {toast && <div className="ca-toast" role="status">{toast}</div>}
    </div>
  </div>
}

function ArticleSection({ section, locations, bookmarks, notes, onBookmark, onSaveNote, onCopy, onJump }) {
  const topicLocations = matchLocations(section, locations)
  const diagrams = diagramsFor(section.title)
  const relation = relationships.find(([name]) => section.title.toLowerCase().includes(name.toLowerCase()))
  return <section id={section.id} data-topic-id={section.locationIds[0] || ''} className={`ca-source-section level-${section.level}`}>
    <div className="ca-topic-heading">
      <div><span className="ca-section-kind">{section.question ? 'QUESTION / EXPLANATION' : section.level === 2 ? 'CHAPTER' : 'TOPIC'}</span><h2>{section.title}</h2>{section.repeated && <span className="ca-repeat-badge">Repeated in source · preserved</span>}</div>
      <div className="ca-topic-actions"><button className={bookmarks.includes(section.id) ? 'is-bookmarked' : ''} onClick={() => onBookmark(section.id)} aria-label={bookmarks.includes(section.id) ? 'Remove bookmark' : 'Bookmark topic'}>{bookmarks.includes(section.id) ? '★' : '☆'}</button><button onClick={() => onCopy(section.id)} aria-label="Copy deep link">↗</button></div>
    </div>
    <div className="ca-markdown" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(section.html) }} />
    {topicLocations.length > 0 && <AtlasMap title={`${section.title} · map context`} locations={topicLocations} onOpenTopic={onJump} />}
    {diagrams.map(([title, chart]) => <MermaidDiagram key={title} title={title} chart={chart} />)}
    {relation && <div className="ca-related"><strong>Related concepts</strong><div>{relation[1].map((item) => <button key={item} onClick={() => onJump(item)}>{item}</button>)}</div></div>}
    <details className="ca-personal-note"><summary>{notes[section.id] ? 'Your note' : 'Add a personal note'}</summary><textarea value={notes[section.id] || ''} onChange={(event) => onSaveNote(section.id, event.target.value)} placeholder="Private note saved in this browser" /></details>
  </section>
}

function RevisionView({ onJump, onTopic, locations }) {
  const [filter, setFilter] = useState('All')
  const types = ['All', ...new Set(revisionFacts.map(([type]) => type))]
  const facts = filter === 'All' ? revisionFacts : revisionFacts.filter(([type]) => type === filter)
  return <section className="ca-revision-view">
    <div className="ca-section-heading"><div><span className="ca-eyebrow">FAST RECALL</span><h2>Revision mode</h2></div><span className="ca-pill">11 Nov 2026</span></div>
    <label className="ca-revision-filter">Filter facts<select value={filter} onChange={(event) => setFilter(event.target.value)}>{types.map((type) => <option key={type}>{type}</option>)}</select></label>
    <div className="ca-revision-facts">{facts.map(([type, text]) => <button key={type} onClick={() => onJump(text)}><small>{type}</small><span>{text}</span><b>Review source →</b></button>)}</div>
    <div className="ca-section-heading"><div><span className="ca-eyebrow">CLICK A NODE TO NAVIGATE</span><h2>Topic map</h2></div></div>
    <TopicMap onJump={onTopic} />
    <div className="ca-section-heading"><div><span className="ca-eyebrow">GEOGRAPHY</span><h2>Important places</h2></div></div>
    <div className="ca-revision-locations">{locations.filter((place) => place.latitude !== null).map((place) => <button key={place.id} onClick={() => onTopic(place.relatedTopics[0])}><span>{place.name}</span><small>{[place.state, place.country].filter(Boolean).join(' · ')}</small></button>)}</div>
    <AtlasMap locations={locations} onOpenTopic={onTopic} />
  </section>
}
