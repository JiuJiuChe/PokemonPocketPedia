# Pocket Deckbuilding Heuristics (Community-Guided)

Use this file only when the request involves deck building or tuning.
Treat these as priors, then validate with local artifacts.

## Core Construction Principles
- Start from one clear win condition and assign each slot to a role:
  - main attacker
  - setup
  - pivot
  - draw/search
  - disruption
  - finisher
- Use a baseline slot skeleton first, then tune:
  - Start near `8-12 Pokemon` and `8-12 Trainer` in a 20-card list.
  - If setup misses occur, increase consistency Trainers before adding extra attackers.
- Optimize for consistency in a 20-card/2-copy format:
  - Prefer fewer evolution branches.
  - Avoid stacking too many independent packages in one list.
- Keep Energy requirements simple:
  - Multi-type plans increase variance in Energy availability and sequencing.
- Build for point-race math, not Prize mapping:
  - Account for ex liability and KO breakpoints to reach 3 points.
- Protect bench economy (3 slots):
  - Avoid low-impact bench sitters.
  - Prefer role-compressed support.
- Maintain Trainer density for setup + interaction:
  - Avoid overloading attackers that cannot be powered on curve.
- Add meta tech slots only after the core engine is stable.

## Tempo And Opening Plan
- Respect first-player tempo constraints when evaluating openers.
- Target at least one extra Basic on bench early:
  - reduces early-loss risk
  - unlocks faster evolution lines
- Include low-cost early actions and recovery lines for slow starts.

## Evolution Chain + Rare Candy Decisions
- Treat Rare Candy as Stage-2 acceleration, not an automatic replacement for Stage 1.
- Respect Rare Candy timing constraints:
  - Cannot use on your first turn.
  - Cannot use on a Basic played that same turn.
- Baseline Stage-2 package:
  - `2 Basic / 2 Stage 2 / 2 Rare Candy`
  - Add `1 Stage 1` when early consistency matters.
  - Add `2 Stage 1` only if Stage 1 has meaningful standalone value or setup is very sensitive.
- Practical tradeoff from community simulation (with `2 Rare Candy`):
  - Turn-3 Stage-2 setup rises from about `44.66%` (0 Stage 1)
  - to `51.16%` (1 Stage 1)
  - to `56.11%` (2 Stage 1)
  - First Stage 1 copy gives larger gain than second copy.
- Archetype bias for Stage 1 count:
  - Fast tempo lists: prefer `0-1` Stage 1.
  - Midrange/control lists: prefer `1-2` Stage 1.
- Prefer Rare Candy targets that attack immediately or next turn after evolving.
- Avoid overcommitting to multiple heavy Stage-2 chains in one 20-card list.

## Stage-2 Chain Selection Checklist
- Immediate payoff after evolution:
  - Attack, ability, or board swing right away.
- Energy-to-impact ratio:
  - Can it function on curve after Rare Candy?
- Stage-1 fallback value:
  - Does Stage 1 still do something useful without Candy?
- Search compatibility:
  - Can your engine find Basic + Stage 2 + Rare Candy reliably?
- Slot pressure:
  - Can the chain fit without cutting core consistency pieces?

## Iteration Loop
- Review losses by cause:
  - draw
  - sequence
  - matchup
  - list structure
- Adjust 1-2 cards at a time.
- Avoid full rebuilds after short losing streaks.

## Confidence Notes
- Community sources can conflict on specific rule wording (for example 2-type vs 3-type Energy claims).
- When a recommendation depends on disputed wording:
  - mark `rule-confidence: medium`
  - prefer current in-client behavior
