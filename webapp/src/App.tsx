import { useEffect, useMemo, useRef, useState } from 'react'

type TabKey = 'home' | 'builder'
type BuilderView = 'builder' | 'analysis'

type CardItem = {
  card_id: string
  name: string
  image?: string | null
  category?: string | null
  trainer_type?: string | null
  stage?: string | null
}

type SelectedCard = {
  card_id: string
  name: string
  count: number
}

type CardUsage = {
  avg_presence_rate?: number | null
  decks_seen?: number | null
  weighted_share_points?: number | null
  sample_decks_seen?: number | null
  sample_max_presence_rate?: number | null
}

type DeckCardDetailsItem = {
  requested_card_id: string
  resolved_card_id?: string | null
  selected_count: number
  found: boolean
  name?: string | null
  set_id?: string | null
  category?: string | null
  trainer_type?: string | null
  stage?: string | null
  hp?: number | null
  image?: string | null
  usage?: CardUsage | null
}

type InteractiveAnalysisOutput = {
  executive_summary?: string
  composition_assessment?: string
  consistency_assessment?: string
  meta_matchups?: string
  alternatives_and_risks?: string[]
  completion_plan?: string
  recommended_additions?: Array<{
    card_name?: string
    count?: number
    reason?: string
  }>
  confidence_and_limitations?: string
}

type InteractiveUsage = {
  input_tokens?: number | null
  output_tokens?: number | null
}

type InteractiveActionResult = {
  mode: 'evaluation' | 'completion'
  model?: string
  usage?: InteractiveUsage
  output?: InteractiveAnalysisOutput
  remaining_slots?: number
}

type ChatTurn = {
  role: 'assistant' | 'user'
  content: string
}

type SavedDeck = {
  id: string
  name: string
  cards: SelectedCard[]
  created_at: string
}

type SnapshotReport = {
  snapshot_date: string
  meta_overview: string | null
  deck_reports: Array<{ filename: string; url: string; deck_slug: string }>
}

type ReportSnapshotsResponse = {
  total: number
  items: SnapshotReport[]
}

const SAVED_DECKS_KEY = 'pokepocketpedia.saved_decks.v1'

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`)
  }
  return (await res.json()) as T
}

function totalCount(cards: SelectedCard[]): number {
  return cards.reduce((acc, item) => acc + item.count, 0)
}

function normalizeCardImageUrl(raw: string | null | undefined): string | null {
  if (!raw) {
    return null
  }
  const url = raw.trim()
  if (!url) {
    return null
  }
  if (url.endsWith('/high') || url.endsWith('/low')) {
    return `${url}.webp`
  }
  if (url.includes('assets.tcgdex.net') && !url.endsWith('.webp')) {
    return `${url}/high.webp`
  }
  return url
}

function formatAnalysisAsText(output: InteractiveAnalysisOutput | undefined): string {
  if (!output) {
    return 'No analysis output.'
  }
  const parts = [
    `Summary: ${output.executive_summary ?? 'N/A'}`,
    `Deck Structure: ${output.composition_assessment ?? 'N/A'}`,
    `Consistency: ${output.consistency_assessment ?? 'N/A'}`,
    `Matchups: ${output.meta_matchups ?? 'N/A'}`,
  ]
  const risks = output.alternatives_and_risks ?? []
  if (risks.length > 0) {
    parts.push(`Alternatives and Risks: ${risks.join(' | ')}`)
  }
  if (output.completion_plan) {
    parts.push(`Completion Plan: ${output.completion_plan}`)
  }
  const additions = output.recommended_additions ?? []
  if (additions.length > 0) {
    parts.push(
      `Recommended Additions: ${additions
        .map((item) => `${item.card_name ?? 'Unknown'} x${item.count ?? 1} (${item.reason ?? 'N/A'})`)
        .join(' | ')}`,
    )
  }
  parts.push(`Confidence and Limitations: ${output.confidence_and_limitations ?? 'N/A'}`)
  return parts.join('\n\n')
}

function renderMarkdownToHtml(markdown: string): string {
  const escaped = markdown
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  const lines = escaped.split('\n')
  const out: string[] = []
  let inList = false
  let inCode = false

  for (const rawLine of lines) {
    const line = rawLine.trimEnd()

    if (line.startsWith('```')) {
      if (inCode) {
        out.push('</code></pre>')
        inCode = false
      } else {
        out.push('<pre><code>')
        inCode = true
      }
      continue
    }
    if (inCode) {
      out.push(`${line}\n`)
      continue
    }

    if (!line.trim()) {
      if (inList) {
        out.push('</ul>')
        inList = false
      }
      continue
    }

    const headingMatch = line.match(/^(#{1,3})\s+(.*)$/)
    if (headingMatch) {
      if (inList) {
        out.push('</ul>')
        inList = false
      }
      const level = headingMatch[1].length
      const text = headingMatch[2]
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
      out.push(`<h${level}>${text}</h${level}>`)
      continue
    }

    const listMatch = line.match(/^[-*]\s+(.*)$/)
    if (listMatch) {
      if (!inList) {
        out.push('<ul>')
        inList = true
      }
      const text = listMatch[1]
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
      out.push(`<li>${text}</li>`)
      continue
    }

    if (inList) {
      out.push('</ul>')
      inList = false
    }

    const paragraph = line
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
    out.push(`<p>${paragraph}</p>`)
  }

  if (inList) {
    out.push('</ul>')
  }
  if (inCode) {
    out.push('</code></pre>')
  }
  return out.join('')
}

export default function App() {
  const [tab, setTab] = useState<TabKey>('home')
  const [builderView, setBuilderView] = useState<BuilderView>('builder')

  const [reportItems, setReportItems] = useState<SnapshotReport[]>([])
  const [selectedSnapshot, setSelectedSnapshot] = useState<string | null>(null)
  const [reportErr, setReportErr] = useState<string | null>(null)

  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState<CardItem[]>([])
  const [searchErr, setSearchErr] = useState<string | null>(null)

  const [selectedCards, setSelectedCards] = useState<SelectedCard[]>([])
  const [savedDeckName, setSavedDeckName] = useState('')
  const [savedDecks, setSavedDecks] = useState<SavedDeck[]>([])

  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [actionResult, setActionResult] = useState<InteractiveActionResult | null>(null)
  const [selectionMessage, setSelectionMessage] = useState<string | null>(null)
  const [cardDetails, setCardDetails] = useState<DeckCardDetailsItem[]>([])
  const [detailsErr, setDetailsErr] = useState<string | null>(null)
  const [loadingDetails, setLoadingDetails] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [chatLoading, setChatLoading] = useState(false)

  const [chatTurns, setChatTurns] = useState<ChatTurn[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatErr, setChatErr] = useState<string | null>(null)

  const [activeReportUrl, setActiveReportUrl] = useState<string | null>(null)
  const [activeReportLabel, setActiveReportLabel] = useState<string>('Weekly Report')
  const [activeDeckSlug, setActiveDeckSlug] = useState<string | null>(null)
  const [showBackToMeta, setShowBackToMeta] = useState(false)
  const [iframeHeight, setIframeHeight] = useState<number>(900)
  const reportFrameRef = useRef<HTMLIFrameElement | null>(null)
  const chatPaneRef = useRef<HTMLDivElement | null>(null)

  const selectedTotal = useMemo(() => totalCount(selectedCards), [selectedCards])

  useEffect(() => {
    try {
      const raw = localStorage.getItem(SAVED_DECKS_KEY)
      if (!raw) {
        return
      }
      const payload = JSON.parse(raw)
      if (Array.isArray(payload)) {
        const decks = payload.filter((item) => item && typeof item === 'object') as SavedDeck[]
        setSavedDecks(decks)
      }
    } catch {
      setSavedDecks([])
    }
  }, [])

  useEffect(() => {
    localStorage.setItem(SAVED_DECKS_KEY, JSON.stringify(savedDecks))
  }, [savedDecks])

  useEffect(() => {
    getJson<ReportSnapshotsResponse>('/api/reports/snapshots')
      .then((data) => {
        setReportItems(data.items ?? [])
        if (data.items?.[0]) {
          const first = data.items[0]
          setSelectedSnapshot(first.snapshot_date)
          if (first.meta_overview) {
            setActiveReportUrl(first.meta_overview)
            setActiveReportLabel(`${first.snapshot_date} meta overview`)
            setActiveDeckSlug(null)
            setShowBackToMeta(false)
          }
        }
      })
      .catch((err: Error) => setReportErr(err.message))
  }, [])

  const selectedReport = useMemo(
    () => reportItems.find((item) => item.snapshot_date === selectedSnapshot) ?? null,
    [reportItems, selectedSnapshot],
  )

  function resizeReportFrame() {
    const frame = reportFrameRef.current
    if (!frame) return
    try {
      const doc = frame.contentDocument
      if (!doc) return
      const nextHeight = Math.max(doc.body?.scrollHeight ?? 0, doc.documentElement?.scrollHeight ?? 0, 720)
      setIframeHeight(nextHeight + 16)
    } catch {
      setIframeHeight(900)
    }
  }

  function syncReportContextFromFrame() {
    const frame = reportFrameRef.current
    if (!frame) return
    try {
      const href = frame.contentWindow?.location?.href ?? ''
      if (!href) return
      const url = new URL(href)
      const filename = url.pathname.split('/').pop() ?? ''
      if (
        filename.startsWith('recommendation.') &&
        filename.endsWith('.html')
      ) {
        const slug = filename.replace('recommendation.', '').replace('.html', '')
        setActiveDeckSlug(slug)
        setShowBackToMeta(true)
        setActiveReportLabel(slug)
        return
      }
      if (filename === 'meta_overview.html') {
        setActiveDeckSlug(null)
        setShowBackToMeta(false)
        if (selectedSnapshot) {
          setActiveReportLabel(`${selectedSnapshot} meta overview`)
        }
      }
    } catch {
      // Ignore cross-origin or transient iframe navigation errors.
    }
  }

  useEffect(() => {
    const q = search.trim()
    if (!q) {
      setSearchResults([])
      setSearchErr(null)
      return
    }
    const timer = window.setTimeout(() => {
      getJson<{ items: CardItem[] }>(`/api/cards?q=${encodeURIComponent(q)}&limit=20`)
        .then((data) => {
          setSearchResults(data.items ?? [])
          setSearchErr(null)
        })
        .catch((err: Error) => {
          setSearchErr(err.message)
          setSearchResults([])
        })
    }, 250)

    return () => window.clearTimeout(timer)
  }, [search])

  function addCard(card: CardItem, nextCount: number) {
    setSelectionMessage(null)
    setSelectedCards((prev) => {
      const existing = prev.find((item) => item.card_id === card.card_id)
      const existingCount = existing?.count ?? 0
      const totalNow = prev.reduce((acc, item) => acc + item.count, 0)
      const totalNext = totalNow - existingCount + nextCount
      if (totalNext > 20) {
        setSelectionMessage('Deck cannot exceed 20 cards.')
        return prev
      }

      const cardNameNorm = card.name.trim().toLowerCase()
      const sameNameNow = prev.reduce((acc, item) => {
        if (item.name.trim().toLowerCase() !== cardNameNorm) {
          return acc
        }
        if (existing && item.card_id === existing.card_id) {
          return acc
        }
        return acc + item.count
      }, 0)
      const sameNameNext = sameNameNow + nextCount
      if (sameNameNext > 2) {
        setSelectionMessage(`Cannot add more than 2 copies of "${card.name}".`)
        return prev
      }

      if (existing) {
        return prev.map((item) => (item.card_id === card.card_id ? { ...item, count: nextCount } : item))
      }
      return [...prev, { card_id: card.card_id, name: card.name, count: nextCount }]
    })
  }

  function removeCard(cardId: string) {
    setSelectionMessage(null)
    setSelectedCards((prev) => prev.filter((item) => item.card_id !== cardId))
  }

  function candidateStatus(card: CardItem): string {
    const trainer = (card.trainer_type ?? '').trim()
    if (trainer) {
      return trainer
    }
    const stage = (card.stage ?? '').trim()
    if (stage) {
      return stage
    }
    return card.category ?? 'Unknown'
  }

  function cardStatus(item: DeckCardDetailsItem): string {
    if (!item.found) {
      return 'Not found'
    }
    const trainer = (item.trainer_type ?? '').trim()
    if (trainer) {
      return trainer
    }
    const stage = (item.stage ?? '').trim()
    if (stage) {
      return stage
    }
    return item.category ?? 'Unknown'
  }

  useEffect(() => {
    if (selectedCards.length === 0) {
      setCardDetails([])
      setDetailsErr(null)
      setLoadingDetails(false)
      return
    }

    let cancelled = false
    const timer = window.setTimeout(async () => {
      setLoadingDetails(true)
      setDetailsErr(null)
      try {
        const res = await fetch('/api/interactive/deck-card-details', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ cards: selectedCards.map(({ card_id, count }) => ({ card_id, count })) }),
        })
        const data = (await res.json()) as { detail?: string; items?: DeckCardDetailsItem[] }
        if (!res.ok) {
          if (!cancelled) {
            setDetailsErr(data.detail ?? 'Failed to load card details.')
            setCardDetails([])
          }
          return
        }
        if (!cancelled) {
          setCardDetails(data.items ?? [])
        }
      } catch (err) {
        if (!cancelled) {
          setDetailsErr(err instanceof Error ? err.message : 'Unexpected error.')
          setCardDetails([])
        }
      } finally {
        if (!cancelled) {
          setLoadingDetails(false)
        }
      }
    }, 180)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [selectedCards])

  useEffect(() => {
    if (!chatPaneRef.current) {
      return
    }
    chatPaneRef.current.scrollTop = chatPaneRef.current.scrollHeight
  }, [chatTurns])

  async function executeDeckAction(cards: SelectedCard[], openAnalysis: boolean) {
    setActionMessage(null)
    setActionResult(null)
    setChatTurns([])
    const total = totalCount(cards)
    if (total > 20) {
      setActionMessage('Deck cannot exceed 20 cards.')
      return
    }
    if (total === 0) {
      setActionMessage('Select at least one card first.')
      return
    }

    const endpoint = total === 20 ? '/api/interactive/evaluate-deck' : '/api/interactive/complete-deck'
    setActionLoading(true)
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: "openclaw", cards: cards.map(({ card_id, count }) => ({ card_id, count })) }),
      })
      const data = (await res.json()) as {
        detail?: string
        mode?: 'evaluation' | 'completion'
        model?: string
        usage?: InteractiveUsage
        output?: InteractiveAnalysisOutput
        remaining_slots?: number
      }
      if (!res.ok) {
        setActionMessage(data.detail ?? 'Request failed.')
        return
      }

      const result: InteractiveActionResult = {
        mode: data.mode ?? (total === 20 ? 'evaluation' : 'completion'),
        model: data.model,
        usage: data.usage,
        output: data.output,
        remaining_slots: data.remaining_slots,
      }
      setActionResult(result)
      setChatTurns([{ role: 'assistant', content: formatAnalysisAsText(result.output) }])
      if (openAnalysis) {
        setBuilderView('analysis')
      }
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : 'Unexpected error.')
    } finally {
      setActionLoading(false)
    }
  }

  async function runDeckAction() {
    await executeDeckAction(selectedCards, true)
  }

  async function openDeckDetailInAI() {
    if (!activeDeckSlug) {
      return
    }
    setActionMessage(null)
    try {
      const query = selectedSnapshot ? `&snapshot_date=${encodeURIComponent(selectedSnapshot)}` : ''
      const res = await fetch(
        `/api/interactive/deck-template?deck_slug=${encodeURIComponent(activeDeckSlug)}${query}`,
      )
      const data = (await res.json()) as {
        detail?: string
        selected_cards?: Array<{ card_id: string; card_name: string; count: number }>
      }
      if (!res.ok) {
        setActionMessage(data.detail ?? 'Failed to load deck template.')
        return
      }
      const cards: SelectedCard[] = (data.selected_cards ?? []).map((item) => ({
        card_id: item.card_id,
        name: item.card_name,
        count: item.count,
      }))
      if (cards.length === 0) {
        setActionMessage('No cards found for this deck template.')
        return
      }
      setSelectedCards(cards)
      setTab('builder')
      setBuilderView('builder')
      await executeDeckAction(cards, true)
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : 'Unexpected error.')
    }
  }

  async function submitChatTurn() {
    const text = chatInput.trim()
    if (!text) {
      return
    }
    if (!actionResult) {
      setChatErr('Run AI evaluation/completion first.')
      return
    }
    const nextTurns = [...chatTurns, { role: 'user' as const, content: text }]
    setChatTurns(nextTurns)
    setChatInput('')
    setChatErr(null)
    setChatLoading(true)
    try {
      const res = await fetch('/api/interactive/chat-turn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: "openclaw",
          mode: actionResult.mode,
          cards: selectedCards.map(({ card_id, count }) => ({ card_id, count })),
          history: chatTurns,
          message: text,
        }),
      })
      const data = (await res.json()) as {
        detail?: string
        reply?: string
        usage?: InteractiveUsage
      }
      if (!res.ok) {
        setChatErr(data.detail ?? 'Failed to get chat reply.')
        return
      }
      setChatTurns((prev) => [...prev, { role: 'assistant', content: data.reply ?? 'N/A' }])
    } catch (err) {
      setChatErr(err instanceof Error ? err.message : 'Unexpected error.')
    } finally {
      setChatLoading(false)
    }
  }

  function saveCurrentDeck() {
    const name = savedDeckName.trim()
    if (!name) {
      setSelectionMessage('Enter a deck name first.')
      return
    }
    if (selectedCards.length === 0) {
      setSelectionMessage('Select cards before saving a deck.')
      return
    }
    const next: SavedDeck = {
      id: `${Date.now()}`,
      name,
      cards: selectedCards,
      created_at: new Date().toISOString(),
    }
    setSavedDecks((prev) => [next, ...prev].slice(0, 30))
    setSavedDeckName('')
    setSelectionMessage(`Saved deck "${name}".`)
  }

  function loadSavedDeck(deck: SavedDeck) {
    setSelectedCards(deck.cards)
    setBuilderView('builder')
    setActionMessage(null)
    setActionResult(null)
    setChatTurns([])
    setChatErr(null)
    setSelectionMessage(`Loaded deck "${deck.name}".`)
  }

  function deleteSavedDeck(deckId: string) {
    setSavedDecks((prev) => prev.filter((item) => item.id !== deckId))
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <h1>PokePocketPedia</h1>
      </header>

      <nav className="tabs">
        <button className={tab === 'home' ? 'tab active' : 'tab'} onClick={() => setTab('home')}>
          Home
        </button>
        <button className={tab === 'builder' ? 'tab active' : 'tab'} onClick={() => setTab('builder')}>
          Deck Builder
        </button>
      </nav>

      {tab === 'home' && (
        <section className="panel">
          {reportErr && <p className="error">{reportErr}</p>}
          {reportItems.length === 0 && !reportErr && <p>Loading reports...</p>}
          {reportItems.length > 0 && (
            <>
              <div className="home-layout">
                <aside className="report-sidebar">
                  <h3>Reports</h3>
                  <ul className="snapshot-list">
                    {reportItems.map((item) => (
                      <li key={item.snapshot_date}>
                        <button
                          className={item.snapshot_date === selectedSnapshot ? 'snapshot-btn active' : 'snapshot-btn'}
                          onClick={() => {
                            setSelectedSnapshot(item.snapshot_date)
                            if (item.meta_overview) {
                              setActiveReportUrl(item.meta_overview)
                              setActiveReportLabel(`${item.snapshot_date} meta overview`)
                              setActiveDeckSlug(null)
                              setShowBackToMeta(false)
                            } else {
                              setActiveReportUrl(null)
                            }
                          }}
                        >
                          {item.snapshot_date}
                        </button>
                      </li>
                    ))}
                  </ul>
                </aside>

                <div className="report-main">
                  {activeReportUrl ? (
                    <>
                      <div className="report-toolbar">
                        {showBackToMeta && selectedReport?.meta_overview && (
                          <button
                            className="back-btn"
                            onClick={() => {
                              setActiveReportUrl(selectedReport.meta_overview)
                              setActiveReportLabel(`${selectedReport.snapshot_date} meta overview`)
                              setActiveDeckSlug(null)
                              setShowBackToMeta(false)
                            }}
                          >
                            Back to Meta Overview
                          </button>
                        )}
                        {showBackToMeta && activeDeckSlug && (
                          <button
                            className="primary report-ai-btn"
                            onClick={() => void openDeckDetailInAI()}
                          >
                            ✨ ask AI
                          </button>
                        )}
                      </div>
                      <iframe
                        ref={reportFrameRef}
                        className="report-frame"
                        src={activeReportUrl}
                        title={activeReportLabel}
                        style={{ height: `${iframeHeight}px` }}
                        scrolling="no"
                        onLoad={() => {
                          resizeReportFrame()
                          syncReportContextFromFrame()
                        }}
                      />
                      {selectedReport && selectedReport.deck_reports.length > 0 && (
                        <section className="deck-links-block">
                          <h3>Deck Details</h3>
                          <ul className="deck-links">
                            {selectedReport.deck_reports.map((item) => (
                              <li key={item.filename}>
                                <button
                                  className="deck-link-btn"
                                  onClick={() => {
                                    setActiveReportUrl(item.url)
                                    setActiveReportLabel(item.deck_slug)
                                    setActiveDeckSlug(item.deck_slug)
                                    setShowBackToMeta(true)
                                  }}
                                >
                                  {item.deck_slug}
                                </button>
                              </li>
                            ))}
                          </ul>
                        </section>
                      )}
                    </>
                  ) : (
                    <p>No report selected.</p>
                  )}
                </div>
              </div>
            </>
          )}
        </section>
      )}

      {tab === 'builder' && builderView === 'builder' && (
        <section className="panel">
          <h2>Select a full deck</h2>
          <p>Search cards, add counts, and review card stats before asking AI for completion/evaluation.</p>
          <div className="builder-layout">
            <div className="builder-left">
              <div className="save-deck-box">
                <input
                  value={savedDeckName}
                  onChange={(e) => setSavedDeckName(e.target.value)}
                  placeholder="Deck name"
                />
                <button onClick={saveCurrentDeck}>Save deck</button>
              </div>
              <ul className="saved-deck-list">
                {savedDecks.map((deck) => (
                  <li key={deck.id}>
                    <button className="saved-deck-load" onClick={() => loadSavedDeck(deck)}>{deck.name}</button>
                    <button className="saved-deck-delete" onClick={() => deleteSavedDeck(deck.id)}>Delete</button>
                  </li>
                ))}
              </ul>

              <div className="search-row">
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search cards by name or text..."
                />
                {searchErr && <span className="error">{searchErr}</span>}
                {selectionMessage && <span className="error">{selectionMessage}</span>}
              </div>

              <div className="search-grid">
                {searchResults.map((card) => (
                  <article className="card-result" key={card.card_id}>
                    {card.image ? (
                      <img className="card-result-image" src={normalizeCardImageUrl(card.image) ?? undefined} alt={card.name} />
                    ) : (
                      <div className="card-result-noimg">No image</div>
                    )}
                    <p className="card-name">{card.name}</p>
                    <p className="card-result-status">{candidateStatus(card)}</p>
                    <div className="card-actions">
                      <button onClick={() => addCard(card, 1)}>Add x1</button>
                      <button onClick={() => addCard(card, 2)}>Add x2</button>
                    </div>
                  </article>
                ))}
              </div>

              <div className="action-stack">
                <button className="primary" onClick={runDeckAction} disabled={selectedTotal > 20 || actionLoading}>
                  ✨ ask AI
                </button>
                {actionLoading && (
                  <p className="loading-inline loading-below">
                    <span className="spinner" /> Waiting for AI response...
                  </p>
                )}
              </div>
              {actionMessage && <p className="message">{actionMessage}</p>}
            </div>

            <div className="builder-right">
              <div className="selected-header">
                <h3>Selected Cards</h3>
                <button
                  className="clear-btn"
                  onClick={() => {
                    setSelectedCards([])
                    setActionMessage(null)
                    setActionResult(null)
                    setSelectionMessage(null)
                    setCardDetails([])
                    setDetailsErr(null)
                    setChatTurns([])
                    setChatErr(null)
                  }}
                >
                  Clear all
                </button>
              </div>
              <p>Total selected: {selectedTotal} / 20</p>
              {loadingDetails && <p>Loading selected card details...</p>}
              {detailsErr && <p className="error">{detailsErr}</p>}
              <div className="card-details-grid">
                {selectedCards.map((item) => {
                  const details = cardDetails.find((row) => row.requested_card_id === item.card_id)
                  return (
                    <article className="card-detail" key={item.card_id}>
                      {details?.image ? (
                        <img src={details.image} alt={details.name ?? item.name} />
                      ) : (
                        <div className="card-detail-noimg">No image</div>
                      )}
                      <h4>{details?.name ?? item.name}</h4>
                      <p>
                        Status:{' '}
                        {cardStatus(
                          details ?? {
                            requested_card_id: item.card_id,
                            selected_count: item.count,
                            found: false,
                          },
                        )}
                      </p>
                      <p>
                        Meta presence:{' '}
                        {typeof details?.usage?.avg_presence_rate === 'number'
                          ? `${(details.usage.avg_presence_rate * 100).toFixed(1)}%`
                          : 'N/A'}
                      </p>
                      <div className="card-detail-actions">
                        <span className="count-badge">x{item.count}</span>
                        <button onClick={() => removeCard(item.card_id)}>Remove</button>
                      </div>
                    </article>
                  )
                })}
              </div>
            </div>
          </div>
        </section>
      )}

      {tab === 'builder' && builderView === 'analysis' && (
        <section className="panel analysis-panel">
          <div className="analysis-header">
            <h2>AI Deck Analysis</h2>
            <button className="back-btn" onClick={() => setBuilderView('builder')}>
              Back to Deck Builder
            </button>
          </div>

          <div className="analysis-cards-grid">
            {selectedCards.map((item) => {
              const details = cardDetails.find((row) => row.requested_card_id === item.card_id)
              return (
                <article className="analysis-card" key={`analysis-${item.card_id}`}>
                  {details?.image ? (
                    <img src={details.image} alt={details.name ?? item.name} />
                  ) : (
                    <div className="card-detail-noimg">No image</div>
                  )}
                  <span className="count-badge">x{item.count}</span>
                </article>
              )
            })}
          </div>

          <div className="analysis-chat" ref={chatPaneRef}>
            {chatTurns.map((turn, idx) => (
              <div key={`${turn.role}-${idx}`} className={turn.role === 'assistant' ? 'bubble bubble-ai' : 'bubble bubble-user'}>
                <div
                  className="md-content"
                  dangerouslySetInnerHTML={{ __html: renderMarkdownToHtml(turn.content) }}
                />
              </div>
            ))}
            {chatLoading && (
              <div className="bubble bubble-ai loading-inline">
                <span className="spinner" /> Thinking...
              </div>
            )}
          </div>

          <div className="analysis-input-row">
            <input
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Ask a follow-up question about this deck..."
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  void submitChatTurn()
                }
              }}
            />
            <button onClick={() => void submitChatTurn()} disabled={chatLoading || !chatInput.trim()}>
              Send
            </button>
          </div>
          {chatErr && <p className="error">{chatErr}</p>}
        </section>
      )}
    </div>
  )
}
