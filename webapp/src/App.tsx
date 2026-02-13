import { useEffect, useMemo, useRef, useState } from 'react'

type TabKey = 'home' | 'builder'

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

type SnapshotReport = {
  snapshot_date: string
  meta_overview: string | null
  deck_reports: Array<{ filename: string; url: string; deck_slug: string }>
}

type ReportSnapshotsResponse = {
  total: number
  items: SnapshotReport[]
}

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

export default function App() {
  const [tab, setTab] = useState<TabKey>('home')

  const [reportItems, setReportItems] = useState<SnapshotReport[]>([])
  const [selectedSnapshot, setSelectedSnapshot] = useState<string | null>(null)
  const [reportErr, setReportErr] = useState<string | null>(null)

  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState<CardItem[]>([])
  const [searchErr, setSearchErr] = useState<string | null>(null)

  const [selectedCards, setSelectedCards] = useState<SelectedCard[]>([])

  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [selectionMessage, setSelectionMessage] = useState<string | null>(null)
  const [cardDetails, setCardDetails] = useState<DeckCardDetailsItem[]>([])
  const [detailsErr, setDetailsErr] = useState<string | null>(null)
  const [loadingDetails, setLoadingDetails] = useState(false)
  const [activeReportUrl, setActiveReportUrl] = useState<string | null>(null)
  const [activeReportLabel, setActiveReportLabel] = useState<string>('Weekly Report')
  const [showBackToMeta, setShowBackToMeta] = useState(false)
  const [iframeHeight, setIframeHeight] = useState<number>(900)
  const reportFrameRef = useRef<HTMLIFrameElement | null>(null)

  const selectedTotal = useMemo(() => totalCount(selectedCards), [selectedCards])

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
      const nextHeight = Math.max(
        doc.body?.scrollHeight ?? 0,
        doc.documentElement?.scrollHeight ?? 0,
        720,
      )
      setIframeHeight(nextHeight + 16)
    } catch {
      setIframeHeight(900)
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
        return prev.map((item) =>
          item.card_id === card.card_id ? { ...item, count: nextCount } : item,
        )
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
          body: JSON.stringify({
            cards: selectedCards.map(({ card_id, count }) => ({ card_id, count })),
          }),
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

  async function runDeckAction() {
    setActionMessage(null)
    if (selectedTotal > 20) {
      setActionMessage('Deck cannot exceed 20 cards.')
      return
    }
    if (selectedTotal === 0) {
      setActionMessage('Select at least one card first.')
      return
    }
    const endpoint = selectedTotal === 20 ? '/api/interactive/evaluate-deck' : '/api/interactive/complete-deck'
    setLoadingDetails(true)
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cards: selectedCards.map(({ card_id, count }) => ({ card_id, count })),
        }),
      })
      const data = (await res.json()) as { detail?: string; message?: string; remaining_slots?: number }
      if (!res.ok) {
        setActionMessage(data.detail ?? 'Request failed.')
        return
      }
      if (selectedTotal === 20) {
        setActionMessage(data.message ?? 'Deck evaluation placeholder response received.')
      } else {
        const suffix =
          typeof data.remaining_slots === 'number'
            ? ` Remaining slots: ${data.remaining_slots}.`
            : ''
        setActionMessage(`${data.message ?? 'Deck completion placeholder response received.'}${suffix}`)
      }
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : 'Unexpected error.')
    } finally {
      setLoadingDetails(false)
    }
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
        <button
          className={tab === 'builder' ? 'tab active' : 'tab'}
          onClick={() => setTab('builder')}
        >
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
                          className={
                            item.snapshot_date === selectedSnapshot
                              ? 'snapshot-btn active'
                              : 'snapshot-btn'
                          }
                          onClick={() => {
                            setSelectedSnapshot(item.snapshot_date)
                            if (item.meta_overview) {
                              setActiveReportUrl(item.meta_overview)
                              setActiveReportLabel(`${item.snapshot_date} meta overview`)
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
                              setActiveReportLabel(
                                `${selectedReport.snapshot_date} meta overview`,
                              )
                              setShowBackToMeta(false)
                            }}
                          >
                            Back to Meta Overview
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
                        onLoad={resizeReportFrame}
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

      {tab === 'builder' && (
        <section className="panel">
          <h2>Select a full deck</h2>
          <p>Search cards, add counts, and review card stats before asking AI for completion/evaluation.</p>
          <div className="builder-layout">
            <div className="builder-left">
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
                      <img
                        className="card-result-image"
                        src={card.image.endsWith('/high') || card.image.endsWith('/low') ? `${card.image}.webp` : card.image.includes('assets.tcgdex.net') && !card.image.endsWith('.webp') ? `${card.image}/high.webp` : card.image}
                        alt={card.name}
                      />
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

              <button className="primary" onClick={runDeckAction} disabled={selectedTotal > 20 || loadingDetails}>
                {selectedTotal === 20 ? 'AI evaluation' : 'AI completion'}
              </button>
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
                    setSelectionMessage(null)
                    setCardDetails([])
                    setDetailsErr(null)
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
                      <p>Status: {cardStatus(details ?? { requested_card_id: item.card_id, selected_count: item.count, found: false })}</p>
                      <p>Meta presence: {typeof details?.usage?.avg_presence_rate === 'number' ? `${(details.usage.avg_presence_rate * 100).toFixed(1)}%` : 'N/A'}</p>
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
    </div>
  )
}
