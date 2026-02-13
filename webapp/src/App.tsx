import { useEffect, useMemo, useRef, useState } from 'react'

type TabKey = 'home' | 'evaluate' | 'complete'

type CardItem = {
  card_id: string
  name: string
  image?: string | null
}

type SelectedCard = {
  card_id: string
  name: string
  count: number
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

  const [selectedEvaluate, setSelectedEvaluate] = useState<SelectedCard[]>([])
  const [selectedComplete, setSelectedComplete] = useState<SelectedCard[]>([])

  const [evalMessage, setEvalMessage] = useState<string | null>(null)
  const [completeMessage, setCompleteMessage] = useState<string | null>(null)
  const [activeReportUrl, setActiveReportUrl] = useState<string | null>(null)
  const [activeReportLabel, setActiveReportLabel] = useState<string>('Weekly Report')
  const [showBackToMeta, setShowBackToMeta] = useState(false)
  const [iframeHeight, setIframeHeight] = useState<number>(900)
  const reportFrameRef = useRef<HTMLIFrameElement | null>(null)

  const evalTotal = useMemo(() => totalCount(selectedEvaluate), [selectedEvaluate])
  const completeTotal = useMemo(() => totalCount(selectedComplete), [selectedComplete])

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

  function addCard(
    target: 'evaluate' | 'complete',
    card: CardItem,
    nextCount: number,
  ) {
    const setter = target === 'evaluate' ? setSelectedEvaluate : setSelectedComplete
    setter((prev) => {
      const existing = prev.find((item) => item.card_id === card.card_id)
      if (existing) {
        return prev.map((item) =>
          item.card_id === card.card_id ? { ...item, count: nextCount } : item,
        )
      }
      return [...prev, { card_id: card.card_id, name: card.name, count: nextCount }]
    })
  }

  function removeCard(target: 'evaluate' | 'complete', cardId: string) {
    const setter = target === 'evaluate' ? setSelectedEvaluate : setSelectedComplete
    setter((prev) => prev.filter((item) => item.card_id !== cardId))
  }

  async function submitEvaluate() {
    setEvalMessage(null)
    try {
      const res = await fetch('/api/interactive/evaluate-deck', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cards: selectedEvaluate.map(({ card_id, count }) => ({ card_id, count })) }),
      })
      const data = (await res.json()) as { detail?: string; message?: string }
      if (!res.ok) {
        setEvalMessage(data.detail ?? 'Failed to evaluate deck.')
        return
      }
      setEvalMessage(data.message ?? 'Deck evaluation placeholder response received.')
    } catch (err) {
      setEvalMessage(err instanceof Error ? err.message : 'Unexpected error.')
    }
  }

  async function submitComplete() {
    setCompleteMessage(null)
    try {
      const res = await fetch('/api/interactive/complete-deck', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cards: selectedComplete.map(({ card_id, count }) => ({ card_id, count })) }),
      })
      const data = (await res.json()) as {
        detail?: string
        message?: string
        remaining_slots?: number
      }
      if (!res.ok) {
        setCompleteMessage(data.detail ?? 'Failed to complete deck.')
        return
      }
      const suffix =
        typeof data.remaining_slots === 'number'
          ? ` Remaining slots: ${data.remaining_slots}.`
          : ''
      setCompleteMessage(`${data.message ?? 'Deck completion placeholder response received.'}${suffix}`)
    } catch (err) {
      setCompleteMessage(err instanceof Error ? err.message : 'Unexpected error.')
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
          className={tab === 'evaluate' ? 'tab active' : 'tab'}
          onClick={() => setTab('evaluate')}
        >
          Deck Evaluation
        </button>
        <button
          className={tab === 'complete' ? 'tab active' : 'tab'}
          onClick={() => setTab('complete')}
        >
          Deck Completion
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

      {(tab === 'evaluate' || tab === 'complete') && (
        <section className="panel">
          <h2>{tab === 'evaluate' ? 'Evaluate a 20-card deck' : 'Complete a partial deck'}</h2>
          <p>Search cards, add counts, then send to interactive API placeholders.</p>

          <div className="search-row">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search cards by name or text..."
            />
            {searchErr && <span className="error">{searchErr}</span>}
          </div>

          <div className="search-grid">
            {searchResults.map((card) => (
              <article className="card-result" key={card.card_id}>
                <p className="card-name">{card.name}</p>
                <p className="card-id">{card.card_id}</p>
                <div className="card-actions">
                  <button onClick={() => addCard(tab, card, 1)}>Add x1</button>
                  <button onClick={() => addCard(tab, card, 2)}>Add x2</button>
                </div>
              </article>
            ))}
          </div>

          <h3>Selected Cards</h3>
          <ul className="selected-list">
            {(tab === 'evaluate' ? selectedEvaluate : selectedComplete).map((item) => (
              <li key={item.card_id}>
                <span>{item.name}</span>
                <span>{item.count}x</span>
                <button onClick={() => removeCard(tab, item.card_id)}>Remove</button>
              </li>
            ))}
          </ul>

          {tab === 'evaluate' && (
            <>
              <p>Total selected: {evalTotal} / 20</p>
              <button className="primary" onClick={submitEvaluate}>
                Ask LLM to Evaluate (Phase D logic pending)
              </button>
              {evalMessage && <p className="message">{evalMessage}</p>}
            </>
          )}

          {tab === 'complete' && (
            <>
              <p>Total selected: {completeTotal} / 20</p>
              <button className="primary" onClick={submitComplete}>
                Ask LLM to Complete Deck (Phase D logic pending)
              </button>
              {completeMessage && <p className="message">{completeMessage}</p>}
            </>
          )}
        </section>
      )}
    </div>
  )
}
