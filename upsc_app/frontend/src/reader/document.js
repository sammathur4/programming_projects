import { marked } from 'marked'

marked.setOptions({ gfm: true, breaks: false })

const topicRules = [
  ['siddi-community', /siddi|khushbu|darjada|63-kg|dakar/i],
  ['nyoma-airbase', /nyoma|thoise|daulat beg oldi|ladakh airfields/i],
  ['naseem-al-bahr', /naseem al bahr|muscat|oman/i],
  ['anaemia', /anaemia|haemoglobin|hepcidin|ferroportin/i],
  ['vajra-sat', /vajra.sat|foot.and.mouth|sat.1/i],
  ['muhurat-trading', /muhurat trading|chopda pujan|samvat/i],
  ['gulf-california', /gulf of california|vaquita|tibur[oó]n|angel de la guarda/i],
  ['kilauea', /kīlauea|kilauea|hawai/i],
  ['begonia-siangensis', /begonia siangensis|siang river|upper siang/i],
  ['bherjan-sanctuary', /bherjan|borajan|padumoni|tinsukia/i],
  ['ramon-magsaysay', /ramon magsaysay|kiran bedi|manila/i],
  ['chinar-kashmir', /chinar|kashmir|boueen/i],
  ['rahat-mitra', /rahat mitra|myanmar|chennai/i],
  ['india-bangladesh-jrc', /joint rivers commission|dhaka|bangladesh/i],
  ['apec-shenzhen', /apec|shenzhen|guangdong/i],
]

export const topicGroups = [
  { title: 'Society', topics: ['National Education Day', 'Siddi Community', 'Ramon Magsaysay Award'] },
  { title: 'Defence & international relations', topics: ['Nyoma Airbase', 'Naseem Al Bahr', 'VAJRA-SAT', 'RAHAT MITRA'] },
  { title: 'Health & environment', topics: ['Anaemia', 'Gulf of California', 'Kīlauea Volcano'] },
  { title: 'Economy & geography', topics: ['Muhurat Trading', 'Begonia siangensis', 'Bherjan sanctuary', 'APEC 2026'] },
]

export const revisionFacts = [
  ['Date', 'National Education Day is observed on 11 November, Maulana Abul Kalam Azad’s birth anniversary.'],
  ['Sports', 'Khushbu Rajakbhai Darjada (15): silver in the girls’ 63-kg judo category at the Dakar Youth Olympics.'],
  ['Defence', 'Nyoma reference: about 13,700 ft altitude and about 46 km from the LAC; the map does not draw an LAC boundary.'],
  ['Exercise', 'Naseem Al Bahr is a bilateral India–Oman naval exercise, initiated in 1993.'],
  ['Health', 'The note gives WHO haemoglobin thresholds by population group; see the formatted table in Anaemia.'],
  ['Animal health', 'VAJRA-SAT: 83 participants representing 25 States and 3 Union Territories.'],
  ['Markets', 'BSE institutionalised Muhurat Trading in 1957; NSE adopted it in 1992.'],
  ['Defence', 'RAHAT MITRA: India–Myanmar tri-services HADR exercise held in Chennai.'],
  ['Geography', 'Kīlauea is on Hawaiʻi Island; Begonia siangensis is associated with the Siang Valley in Arunachal Pradesh.'],
  ['APEC', 'The note says the 2026 APEC leaders’ meeting is scheduled for Shenzhen on 18–19 November.'],
]

export const relationships = [
  ['Siddi Community', ['Gujarat', 'Karnataka', 'Maharashtra', 'Scheduled Tribe', 'PVTG classification']],
  ['Nyoma Airbase', ['Ladakh', 'Nyoma', 'Leh', 'Thoise', 'Kargil', 'Daulat Beg Oldi', 'LAC context']],
  ['Naseem Al Bahr', ['India–Oman relations', 'Muscat', 'Arabian Sea', 'Indian Ocean Region']],
  ['VAJRA-SAT', ['Foot-and-mouth disease', 'Animal husbandry', 'Biosecurity', 'Disease surveillance']],
  ['Anaemia', ['Iron metabolism', 'Nutrition', 'Public health', 'Hepcidin–ferroportin']],
  ['Gulf of California', ['Vaquita', 'Marine biodiversity', 'Baja California Peninsula']],
  ['Kīlauea Volcano', ['Hawaiʻi Island', 'Hotspot volcanism', 'Pacific Plate']],
  ['Begonia siangensis', ['Upper Siang', 'Siang River Valley', 'Eastern Himalayas']],
]

export function slugify(value) {
  return value.toLowerCase().normalize('NFKD').replace(/[^\w\s-]/g, '').trim().replace(/[\s_-]+/g, '-')
}

function formatWhoTable(body) {
  const lines = body.split('\n')
  const header = lines.findIndex((line) => line.includes('Population Group') && line.includes('Anaemia if Hb is Below'))
  if (header < 0) return body

  const rows = []
  for (let i = header + 1; i < lines.length; i += 1) {
    const match = lines[i].match(/^(.+?)\s+(\d+(?:\.\d+)?)\s*g\/dL\s*$/i)
    if (!match) break
    rows.push(`| ${match[1].trim()} | ${match[2]} g/dL |`)
  }
  if (!rows.length) return body

  lines.splice(header, rows.length + 1,
    '| Population group | Haemoglobin threshold |',
    '|---|---:|',
    ...rows)
  return lines.join('\n')
}

export function normalizeSource(markdown) {
  let body = markdown.replace(/^---\n[\s\S]*?\n---\n/, '')
  body = body.replace(/\n## Revision maps\n[\s\S]*$/, '')
  body = body.replace(/^# 11 November 2026.*\n+/m, '')
  body = body.replace(
    /Normal Haemoglobin Levels and WHO\s*\nClassificationWHO uses/i,
    '### Normal haemoglobin levels and WHO classification\n\nWHO uses',
  )
  return formatWhoTable(body)
}

export function parseDocument(markdown) {
  const frontmatter = markdown.match(/^---\n([\s\S]*?)\n---\n/)
  const title = frontmatter?.[1].match(/^title:\s*["']?(.+?)["']?\s*$/m)?.[1] || 'Current affairs'
  const body = normalizeSource(markdown)
  const sections = []
  const usedIds = new Map()
  let current = null

  const flush = () => {
    if (!current) return
    const content = current.markdown.replace(/^#{1,3}[^\n]*\n?/, '')
    current.html = marked.parse(content)
    current.text = current.html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
    current.question = /^(?:ANSWER\b|Correct Answer\b)/i.test(current.title)
    sections.push(current)
  }

  for (const token of marked.lexer(body)) {
    if (token.type === 'heading' && token.depth === 1) continue
    if (token.type === 'heading' && token.depth <= 3) {
      flush()
      const base = slugify(token.text) || `section-${sections.length + 1}`
      const count = usedIds.get(base) || 0
      usedIds.set(base, count + 1)
      current = {
        title: token.text,
        level: token.depth,
        id: count ? `${base}-${count + 1}` : base,
        markdown: token.raw,
      }
      continue
    }
    if (!current) current = { title: 'Overview', level: 2, id: 'overview', markdown: '' }
    current.markdown += token.raw
  }
  flush()

  const paragraphs = new Map()
  sections.forEach((section) => {
    const plain = section.text.toLowerCase().replace(/\W+/g, ' ').trim()
    if (plain.length > 90) paragraphs.set(plain, (paragraphs.get(plain) || 0) + 1)
  })
  sections.forEach((section) => {
    const plain = section.text.toLowerCase().replace(/\W+/g, ' ').trim()
    section.repeated = plain.length > 90 && (paragraphs.get(plain) || 0) > 1
    section.locationIds = [...new Set(topicRules.filter(([, pattern]) => pattern.test(`${section.title} ${section.text}`)).map(([id]) => id))]
  })

  return { title, sections, body }
}

export function matchLocations(section, locations) {
  return locations.filter((location) => section.locationIds.some((id) => location.relatedTopics.includes(id)))
}

export function tableAsMarkdown(rows) {
  return `| Exercise | Type / participants | Context |\n|---|---|---|\n${rows.map((row) => `| ${row.join(' | ')} |`).join('\n')}`
}
